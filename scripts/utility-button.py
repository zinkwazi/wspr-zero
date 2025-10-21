#!/usr/bin/env python3
import RPi.GPIO as GPIO
import os, time, logging, pwd, subprocess

# ---------------- config ----------------
WSPR_DEFAULT_USER = "wsprzero"
LOG_DIR  = "/opt/wsprzero/wspr-zero/logs"
LOG_FILE = os.path.join(LOG_DIR, "wspr-zero-shutdown.log")

BUTTON_PIN = 19
LED_PIN    = 18
PRESS_INTERVAL = 6    # seconds to allow multi-press counting
HOLD_TIME      = 10    # seconds to trigger shutdown
DELAY_START    = 5   # seconds to delay after boot

CHECKIN_SERVICE = ["/bin/systemctl", "start", "wspr-server-checkin.service"]
SHUTDOWN_CMD    = ["/bin/systemctl", "poweroff", "-i"]

# ------------- identity/ownership -------------
target_user = os.environ.get("WSPR_LOG_USER", WSPR_DEFAULT_USER)
try:
    pw = pwd.getpwnam(target_user)
    UID, GID = pw.pw_uid, pw.pw_gid
except KeyError:
    UID, GID = os.geteuid(), os.getegid()

def safe_chown(path, uid, gid):
    try: os.chown(path, uid, gid)
    except PermissionError: pass

def safe_chmod(path, mode):
    try: os.chmod(path, mode)
    except PermissionError: pass

# ------------- startup -------------
time.sleep(DELAY_START)

os.makedirs(LOG_DIR, exist_ok=True)
safe_chown(LOG_DIR, UID, GID)
safe_chmod(LOG_DIR, 0o2775)  # setgid so group is inherited

open(LOG_FILE, "a").close()
safe_chown(LOG_FILE, UID, GID)
safe_chmod(LOG_FILE, 0o664)

logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format="%(asctime)s %(message)s")

# ------------- GPIO -------------
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(LED_PIN, GPIO.OUT, initial=GPIO.LOW)

button_presses = 0
last_press_time = 0.0

def blink_led(times=20, interval=0.1):
    for _ in range(times):
        GPIO.output(LED_PIN, True);  time.sleep(interval)
        GPIO.output(LED_PIN, False); time.sleep(interval)

def button_callback(channel):
    global button_presses, last_press_time
    now = time.time()
    pressed = (GPIO.input(channel) == 0)  # active-low button

    if pressed:
        if now - last_press_time > PRESS_INTERVAL:
            button_presses = 0
        button_presses += 1
        last_press_time = now

        if button_presses >= 5:
            logging.info("Button pressed 5×: starting setup check-in service")
            try:
                subprocess.Popen(CHECKIN_SERVICE)  # non-blocking
            except Exception as e:
                logging.info(f"Failed to start check-in service: {e}")
            button_presses = 0  # reset sequence
    else:
        # Released
        if last_press_time and (now - last_press_time >= HOLD_TIME) and button_presses == 1:
            logging.info(f"Button held for {HOLD_TIME} seconds. Shutting down…")
            blink_led()
            try:
                subprocess.Popen(SHUTDOWN_CMD)
            except Exception as e:
                logging.info(f"Shutdown command failed: {e}")
        last_press_time = 0.0

GPIO.add_event_detect(BUTTON_PIN, GPIO.BOTH, callback=button_callback, bouncetime=200)

try:
    logging.info(f"Utility button monitor started. Hold {HOLD_TIME}s to shutdown; press 5× for setup.")
    while True:
        time.sleep(86400)
except KeyboardInterrupt:
    logging.info("Program terminated by user")
finally:
    GPIO.cleanup()

