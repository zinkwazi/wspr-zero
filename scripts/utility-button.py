import RPi.GPIO as GPIO
import os, time, logging, pwd, getpass

# --- log setup (user-agnostic, matches server_checkin.py) ---
log_dir = '/opt/wsprzero/wspr-zero/logs'
log_file = os.path.join(log_dir, 'wspr-zero-shutdown.log')

target_user = os.environ.get("WSPR_LOG_USER", getpass.getuser())
try:
    pw = pwd.getpwnam(target_user)
    uid, gid = pw.pw_uid, pw.pw_gid
except KeyError:
    uid, gid = os.geteuid(), os.getegid()

def safe_chown(path, uid, gid):
    try: os.chown(path, uid, gid)
    except PermissionError: pass

def safe_chmod(path, mode):
    try: os.chmod(path, mode)
    except PermissionError: pass

os.makedirs(log_dir, exist_ok=True)
safe_chown(log_dir, uid, gid)
safe_chmod(log_dir, 0o2775)

if not os.path.exists(log_file):
    open(log_file, 'a').close()
safe_chown(log_file, uid, gid)
safe_chmod(log_file, 0o664)

logging.basicConfig(filename=log_file, level=logging.INFO, format='%(asctime)s %(message)s')

# --- pins & timings ---
shutdown_pin = 19
led_pin = 18
press_interval = 6
hold_time = 10    # keep this in sync with your log message

# --- GPIO init ---
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(shutdown_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(led_pin, GPIO.OUT)

...

        if button_presses >= 5:
            logging.info("Button pressed 5 times in a row. Entering Setup Mode.")
            os.system("systemctl start wspr-server-checkin.service")

    elif GPIO.input(channel) == 1:
        if last_press_time and (current_time - last_press_time >= hold_time) and button_presses == 1:
            logging.info(f"Button held for {hold_time} seconds. Shutting down...")
            blink_led()
            os.system("systemctl poweroff -i")   # instead of 'sudo shutdown now -h'

