#!/usr/bin/env python3
import RPi.GPIO as GPIO
import requests
import json
import time
from datetime import datetime, timezone
import threading
import subprocess
import os
import shutil
import re
import hashlib

def get_uptime_str():
    try:
        with open('/proc/uptime','r') as f:
            seconds = int(float(f.readline().split()[0]))
    except Exception:
        return ""
    mins, sec = divmod(seconds, 60)
    hrs,  mins = divmod(mins, 60)
    days, hrs  = divmod(hrs, 24)
    parts = []
    if days: parts.append(f"{days} day{'s' if days!=1 else ''}")
    if hrs:  parts.append(f"{hrs} hour{'s' if hrs!=1 else ''}")
    if mins: parts.append(f"{mins} minute{'s' if mins!=1 else ''}")
    if not parts: parts.append(f"{sec} seconds")
    return ", ".join(parts)

# --- Root-only execution ---
if os.geteuid() != 0:
    print("server_checkin.py must run as root for GPIO and file ownership; aborting.")
    raise SystemExit("Run with sudo (root).")

# GPIO pin for WSPR-zero LED
led_pin = 18

# Server endpoint
server_url = "https://wspr-zero.com/ez-config/server-listener.php"

# Logs (root-owned)
log_dir = '/opt/wsprzero/wspr-zero/logs'
log_file = os.path.join(log_dir, 'setup-post.log')

# Polling window
CHECKIN_WINDOW = int(os.environ.get("WSPR_CHECKIN_WINDOW", "60"))    # seconds
POLL_INTERVAL  = float(os.environ.get("WSPR_POLL_INTERVAL", "3"))    # seconds
if CHECKIN_WINDOW < POLL_INTERVAL + 3:
    CHECKIN_WINDOW = int(POLL_INTERVAL + 3)

def safe_chown(path, uid, gid):
    try: os.chown(path, uid, gid)
    except (PermissionError, FileNotFoundError): pass

def safe_chmod(path, mode):
    try: os.chmod(path, mode)
    except (PermissionError, FileNotFoundError): pass

os.makedirs(log_dir, exist_ok=True)
safe_chown(log_dir, 0, 0)
safe_chmod(log_dir, 0o2775)
if not os.path.exists(log_file):
    open(log_file, 'a').close()
safe_chown(log_file, 0, 0)
safe_chmod(log_file, 0o664)

def log_message(message):
    with open(log_file, 'a') as f:
        f.write(message + '\n' + '-'*50 + '\n')

# Config I/O
def read_wspr_config():
    path = '/opt/wsprzero/wspr-zero/wspr-config.json'
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception as e:
        log_message(f"Failed to read {path}: {e}")
        return {}

def write_wspr_config(existing_data, new_data):
    existing_data.update(new_data)
    path = '/opt/wsprzero/wspr-zero/wspr-config.json'
    try:
        with open(path, 'w') as f:
            json.dump(existing_data, f, indent=4)
    except Exception as e:
        log_message(f"Failed to write {path}: {e}")

# MAC normalization
_mac_pat = re.compile(r'[^0-9A-Fa-f]')
def canonical_mac(mac):
    if not mac: return ""
    hexonly = _mac_pat.sub('', mac).lower()
    if len(hexonly) == 12:
        return ':'.join(hexonly[i:i+2] for i in range(0, 12, 2))
    return mac.strip().lower()

def ensure_canonical_mac_in_config(cfg):
    mac = canonical_mac(cfg.get('MAC_address', ''))
    if mac: cfg['MAC_address'] = mac

# HTTP
def send_data_to_server(data, label="POST"):
    try:
        headers = {'Content-Type': 'application/json'}
        log_message(f"{label} -> server payload:\n{json.dumps(data, indent=4)}")
        response = requests.post(server_url, headers=headers, json=data, timeout=(3, 7))
        if response.status_code == 200:
            try:
                j = response.json()
                log_message(f"{label} <- server response:\n{json.dumps(j, indent=4)}")
                return j
            except Exception as je:
                log_message(f"{label} response JSON decode failed: {je}\nRaw: {response.text[:4000]}")
                return None
        else:
            log_message(f"{label} failed. HTTP {response.status_code}\nBody: {response.text[:4000]}")
            return None
    except Exception as e:
        log_message(f"{label} exception: {str(e)}")
        return None

# ===== GPIO handling =====
gpio = GPIO

def blink_led():
    try:
        while True:
            for _ in range(5):  # rapid blink 5x/sec
                gpio.output(led_pin, gpio.HIGH)
                time.sleep(0.1)
                gpio.output(led_pin, gpio.LOW)
                time.sleep(0.1)
            gpio.output(led_pin, gpio.HIGH)
            time.sleep(0.5)
            gpio.output(led_pin, gpio.LOW)
            time.sleep(0.5)
    except Exception as e:
        log_message(f"Exception occurred in blink_led: {str(e)}")
        try: gpio.output(led_pin, gpio.LOW)
        except Exception: pass

# systemd control
SERVICE_NAME = os.environ.get("WSPR_SERVICE", "wspr-service")
SYSTEMCTL = shutil.which("systemctl") or "systemctl"

def _systemctl(action, timeout=15):
    cmd = [SYSTEMCTL, '--no-pager', action, SERVICE_NAME]
    try:
        p = subprocess.run(cmd, check=True, text=True, capture_output=True, timeout=timeout)
        log_message(f"systemctl {action} {SERVICE_NAME} OK\nstdout:\n{p.stdout}\nstderr:\n{p.stderr}")
        return True
    except FileNotFoundError as e:
        log_message(f"systemctl not found: {e}")
        return False
    except subprocess.CalledProcessError as e:
        log_message(f"systemctl {action} {SERVICE_NAME} failed (exit {e.returncode})\nstdout:\n{e.stdout}\nstderr:\n{e.stderr}")
        return False
    except subprocess.TimeoutExpired:
        log_message(f"systemctl {action} {SERVICE_NAME} timed out after {timeout}s")
        return False

def stop_wspr():
    log_message("Stopping WSPR process via systemd")
    _systemctl('stop')

def start_wspr():
    log_message("Starting WSPR process via systemd")
    _systemctl('start')

# status payload
def build_status_payload(full_cfg):
    keys = [
        "MAC_address","hostname","local_IP_address","public_IP_address",
        "model_number","serial_number","uptime","last_checkin","setup_timestamp",
    ]
    out = {k: v for k, v in full_cfg.items() if k in keys}
    out["MAC_address"] = canonical_mac(full_cfg.get("MAC_address", ""))
    return out

def _hash_obj(o):
    try:
        s = json.dumps(o, sort_keys=True, separators=(',', ':')).encode()
        return hashlib.sha256(s).hexdigest()
    except Exception:
        return None

# ---- main ----
def main():
    global gpio

    # Stop service to free LED pin and pause a bit
    stop_wspr()
    time.sleep(2.0)

    # Init GPIO + verify function
    try:
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(led_pin, GPIO.OUT, initial=GPIO.LOW)

        try:
            fn = GPIO.gpio_function(led_pin)  # 1 means OUTPUT in RPi.GPIO
            if fn != GPIO.OUT:
                log_message(
                    f"GPIO{led_pin} not set to OUTPUT (func={fn}). "
                    "If using GPIO18, ensure 'dtparam=audio=off' in /boot/config.txt, then reboot."
                )
        except Exception:
            pass

        gpio = GPIO
        log_message(f"LED armed on GPIO{led_pin} (BCM).")
    except Exception as e:
        log_message(f"GPIO init failed ({e}); continuing without LED.")
        class _NoGPIO:
            HIGH = 1; LOW = 0
            def output(self,*a,**k): pass
            def cleanup(self): pass
        gpio = _NoGPIO()

    # Start LED thread
    led_thread = threading.Thread(target=blink_led, daemon=True)
    led_thread.start()
    log_message("LED blink thread started.")

    # Prepare config + post
    wspr_config = read_wspr_config()
    ensure_canonical_mac_in_config(wspr_config)
    wspr_config['uptime'] = get_uptime_str()
    wspr_config['setup_timestamp'] = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

    status_payload = build_status_payload(wspr_config)
    server_response = send_data_to_server(status_payload, label="FIRST POST (status-only)")
    if server_response:
        write_wspr_config(wspr_config, server_response)

    # Poll window
    mac_only = {'MAC_address': wspr_config.get('MAC_address', '')}
    deadline = time.monotonic() + CHECKIN_WINDOW
    prev_hash = None
    i = 1
    while time.monotonic() < deadline:
        server_response = send_data_to_server(mac_only, label=f"POLL {i} (MAC-only)")
        if server_response:
            h = _hash_obj(server_response)
            if h and h != prev_hash:
                write_wspr_config(wspr_config, server_response)
                prev_hash = h
        remaining = deadline - time.monotonic()
        if remaining <= 0: break
        time.sleep(min(POLL_INTERVAL, max(0.05, remaining)))
        i += 1

    # Final fetch
    server_response = send_data_to_server(mac_only, label="FINAL FETCH")
    if server_response:
        write_wspr_config(wspr_config, server_response)

    # Restart WSPR
    start_wspr()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            gpio.output(led_pin, gpio.LOW)
            gpio.cleanup()
        except Exception:
            pass

# systemctl tips:
#   sudo systemctl status  wspr-service
#   sudo systemctl start   wspr-service
#   sudo systemctl stop    wspr-service
#   sudo systemctl restart wspr-service

