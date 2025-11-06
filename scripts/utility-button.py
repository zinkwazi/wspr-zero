#!/usr/bin/env python3
import RPi.GPIO as GPIO
import os, time, logging, pwd, subprocess, shutil, threading

# ---------------- config ----------------
WSPR_DEFAULT_USER = "wsprzero"
LOG_DIR  = "/opt/wsprzero/wspr-zero/logs"
LOG_FILE = os.path.join(LOG_DIR, "wspr-zero-shutdown.log")

# Allow overrides via env (so you can change pins without editing code)
BUTTON_PIN = int(os.environ.get("WSPR_BUTTON_PIN", "19"))
LED_PIN    = int(os.environ.get("WSPR_LED_PIN", "18"))

PRESS_INTERVAL = float(os.environ.get("WSPR_PRESS_WINDOW", "12"))  # seconds for multi-press window
HOLD_TIME      = float(os.environ.get("WSPR_HOLD_TIME", "10"))    # long hold to shutdown
DELAY_START    = 5                                                # give the system a moment on boot

SERVICE_NAME   = os.environ.get("WSPR_SERVICE", "wspr-service")
SYSTEMCTL      = shutil.which("systemctl") or "/usr/bin/systemctl"

CHECKIN_SERVICE_CMD = [SYSTEMCTL, "start", "wspr-server-checkin.service"]
SERVICE_STOP_CMD    = [SYSTEMCTL, "stop",  f"{SERVICE_NAME}"]
SERVICE_START_CMD   = [SYSTEMCTL, "start", f"{SERVICE_NAME}"]
SHUTDOWN_CMD        = [SYSTEMCTL, "poweroff", "-i"]

# ------------- identity/ownership -------------
target_user = os.environ.get("WSPR_LOG_USER", WSPR_DEFAULT_USER)
try:
    pw = pwd.getpwnam(target_user)
    UID, GID = pw.pw_uid, pw.pw_gid
except KeyError:
    UID, GID = os.geteuid(), os.getegid()

def _safe_chown(path, uid, gid):
    try: os.chown(path, uid, gid)
    except Exception: pass

def _safe_chmod(path, mode):
    try: os.chmod(path, mode)
    except Exception: pass

# ------------- startup -------------
time.sleep(DELAY_START)

os.makedirs(LOG_DIR, exist_ok=True)
_safe_chown(LOG_DIR, UID, GID)
_safe_chmod(LOG_DIR, 0o2775)  # setgid so group is inherited

open(LOG_FILE, "a").close()
_safe_chown(LOG_FILE, UID, GID)
_safe_chmod(LOG_FILE, 0o664)

logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format="%(asctime)s %(message)s")
logging.info(f"Config: BUTTON_PIN={BUTTON_PIN} LED_PIN={LED_PIN} "
             f"PRESS_WINDOW={int(PRESS_INTERVAL)}s HOLD_TIME={int(HOLD_TIME)}s")

# ------------- GPIO & LED helpers -------------
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# Button input: pull-up, active-low to GND
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

_led_ok = True
def try_claim_led(initial_low=True):
    """Attempt to claim LED pin; set global state accordingly."""
    global _led_ok
    if _led_ok:
        return
    try:
        GPIO.setup(LED_PIN, GPIO.OUT, initial=GPIO.LOW if initial_low else GPIO.HIGH)
        _led_ok = True
        logging.info(f"LED claimed on GPIO{LED_PIN} after freeing resources.")
    except Exception as e:
        _led_ok = False
        logging.info(f"LED still unavailable on GPIO{LED_PIN}: {e}")

# First attempt at boot; failure is fine—we’ll retry after stopping WSPR
try:
    GPIO.setup(LED_PIN, GPIO.OUT, initial=GPIO.LOW)
except Exception as e:
    _led_ok = False
    logging.info(f"LED init failed on GPIO{LED_PIN}: {e}. Will retry after first button press.")

def _led_on():
    if _led_ok:
        try: GPIO.output(LED_PIN, True)
        except Exception: pass

def _led_off():
    if _led_ok:
        try: GPIO.output(LED_PIN, False)
        except Exception: pass

def _blink(times=6, interval=0.1):
    if not _led_ok:
        return
    for _ in range(times):
        _led_on();  time.sleep(interval)
        _led_off(); time.sleep(interval)

# ------------- state -------------
button_presses = 0
last_press_time = 0.0
sequence_deadline = 0.0

service_paused_for_sequence = False   # we stopped wspr-service on first press
action_taken_in_sequence    = False   # setup or shutdown occurred
button_is_down              = False   # tracks physical button state for hold logic
_service_pause_inflight     = False   # async worker currently trying to pause service

def _stop_wspr_once():
    global service_paused_for_sequence, _service_pause_inflight
    if service_paused_for_sequence or _service_pause_inflight:
        return

    def worker():
        global _service_pause_inflight
        logging.info("First press detected: stopping WSPR service to free LED pin.")
        try:
            subprocess.Popen(SERVICE_STOP_CMD)
        except Exception as e:
            logging.info(f"Failed to stop {SERVICE_NAME}: {e}")
        # Give systemd a beat to fully tear down child; then try to claim LED
        time.sleep(1.0)
        for _ in range(5):            # up to ~1s additional retry
            try_claim_led(initial_low=True)
            if _led_ok:
                break
            time.sleep(0.2)
        _blink(4, 0.08)  # quick visual ack if LED available
        _service_pause_inflight = False

    service_paused_for_sequence = True
    _service_pause_inflight = True
    threading.Thread(target=worker, daemon=True).start()

def _restart_wspr_if_needed():
    global service_paused_for_sequence
    if service_paused_for_sequence:
        logging.info("Multi-press window ended with no action; restarting WSPR service.")
        try:
            subprocess.Popen(SERVICE_START_CMD)
        except Exception as e:
            logging.info(f"Failed to start {SERVICE_NAME}: {e}")
        service_paused_for_sequence = False

# ------------- button ISR -------------
def button_callback(channel):
    global button_presses, last_press_time, sequence_deadline
    global action_taken_in_sequence, button_is_down, service_paused_for_sequence
    now = time.time()
    pressed = (GPIO.input(channel) == 0)  # active-low

    if pressed:
        button_is_down = True
        # New sequence if window expired
        if now > sequence_deadline:
            button_presses = 0
            action_taken_in_sequence = False
        button_presses += 1
        last_press_time = now
        sequence_deadline = now + PRESS_INTERVAL
        logging.info(f"Button press counted: {button_presses}")

        # On the first press of this sequence, stop wspr-service and try to claim LED
        if button_presses == 1:
            _stop_wspr_once()

        # 5 presses → setup mode (check-in); wspr-service will be restarted by that unit afterward
        if button_presses >= 5 and not action_taken_in_sequence:
            logging.info("5 presses detected: starting setup check-in service.")
            try:
                subprocess.Popen(CHECKIN_SERVICE_CMD)  # non-blocking
                action_taken_in_sequence = True
                # Setup mode owns service lifecycle; allow future sequences to stop it again
                service_paused_for_sequence = False
            except Exception as e:
                logging.info(f"Failed to start check-in service: {e}")
            # Reset press counter for next sequence
            button_presses = 0
            sequence_deadline = 0.0
            last_press_time = 0.0
    else:
        button_is_down = False
        # On release, check for long-hold shutdown (single press held)
        if last_press_time:
            held = now - last_press_time
            if held >= HOLD_TIME and not action_taken_in_sequence and button_presses == 1:
                logging.info(f"Button held for {int(HOLD_TIME)} seconds: shutting down.")
                _blink(20, 0.05)
                try:
                    subprocess.Popen(SHUTDOWN_CMD)
                    action_taken_in_sequence = True
                    service_paused_for_sequence = False
                except Exception as e:
                    logging.info(f"Shutdown command failed: {e}")
                    # reset + resume normal operation right away
                    action_taken_in_sequence = False
                    _restart_wspr_if_needed()
                    button_presses = 0
                    sequence_deadline = 0.0
                    last_press_time = 0.0
        # we keep last_press_time as-is for non-hold cases; the window logic handles restart

# Use BOTH so we see press (FALLING) and release (RISING) for hold timing
GPIO.add_event_detect(BUTTON_PIN, GPIO.BOTH, callback=button_callback, bouncetime=120)

try:
    logging.info(f"Utility button monitor started. Hold {int(HOLD_TIME)}s to shutdown; press 5× for setup.")
    # Main loop checks sequence timeouts and restarts WSPR if needed
    while True:
        now = time.time()
        if (
            service_paused_for_sequence
            and not action_taken_in_sequence
            and not button_is_down
            and sequence_deadline > 0
            and now > sequence_deadline
        ):
            # No setup/hold happened within the window → resume WSPR automatically
            _restart_wspr_if_needed()
            # Reset for next sequence
            button_presses = 0
            last_press_time = 0.0
            sequence_deadline = 0.0
        time.sleep(0.2)
except KeyboardInterrupt:
    logging.info("Program terminated by user")
finally:
    try:
        _led_off()
        GPIO.cleanup()
    except Exception:
        pass

