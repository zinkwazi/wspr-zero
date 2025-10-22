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

# --- Root-only execution (ensures all file writes & GPIO are done as root) ---
if os.geteuid() != 0:
    print("server_checkin.py must run as root for GPIO and file ownership; aborting.")
    raise SystemExit("Run with sudo (root).")

# GPIO pin for WSPR-zero LED
led_pin = 18

# Define the URL of the remote server
server_url = "https://wspr-zero.com/ez-config/server-listener.php"

# Log directory and file (owned by root)
log_dir = '/opt/wsprzero/wspr-zero/logs'
log_file = os.path.join(log_dir, 'setup-post.log')

# Tunables (env overrides)
CHECKIN_WINDOW = int(os.environ.get("WSPR_CHECKIN_WINDOW", "60"))    # total seconds to poll
POLL_INTERVAL  = float(os.environ.get("WSPR_POLL_INTERVAL", "3"))    # seconds between polls
# sanity
if CHECKIN_WINDOW < POLL_INTERVAL + 3:
    CHECKIN_WINDOW = int(POLL_INTERVAL + 3)

def safe_chown(path, uid, gid):
    try:
        os.chown(path, uid, gid)
    except (PermissionError, FileNotFoundError):
        pass

def safe_chmod(path, mode):
    try:
        os.chmod(path, mode)
    except (PermissionError, FileNotFoundError):
        pass

# Prepare log directory/file (root:root)
os.makedirs(log_dir, exist_ok=True)
safe_chown(log_dir, 0, 0)
safe_chmod(log_dir, 0o2775)

if not os.path.exists(log_file):
    open(log_file, 'a').close()
safe_chown(log_file, 0, 0)
safe_chmod(log_file, 0o664)

def log_message(message):
    with open(log_file, 'a') as file:
        file.write(message + '\n')
        file.write('-' * 50 + '\n')

# Robust read of wspr-config.json
def read_wspr_config():
    path = '/opt/wsprzero/wspr-zero/wspr-config.json'
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception as e:
        log_message(f"Failed to read {path}: {e}")
        return {}

# Write wspr-config.json by merging new_data into existing_data
def write_wspr_config(existing_data, new_data):
    existing_data.update(new_data)
    path = '/opt/wsprzero/wspr-zero/wspr-config.json'
    try:
        with open(path, 'w') as f:
            json.dump(existing_data, f, indent=4)
    except Exception as e:
        log_message(f"Failed to write {path}: {e}")

# ---- MAC normalization ----
_mac_pat = re.compile(r'[^0-9A-Fa-f]')
def canonical_mac(mac):
    """Return lowercase colon-separated MAC, e.g. 'e4:5f:01:50:de:76'."""
    if not mac:
        return ""
    hexonly = _mac_pat.sub('', mac).lower()
    if len(hexonly) == 12:
        return ':'.join(hexonly[i:i+2] for i in range(0, 12, 2))
    return mac.strip().lower()

def ensure_canonical_mac_in_config(cfg):
    mac = canonical_mac(cfg.get('MAC_address', ''))
    if mac:
        cfg['MAC_address'] = mac

# Send data to the server (with response logging)
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
            for _ in range(5):  # Rapid blink 5 times a second
                gpio.output(led_pin, gpio.HIGH)
                time.sleep(0.1)
                gpio.output(led_pin, gpio.LOW)
                time.sleep(0.1)
            gpio.output(led_pin, gpio.HIGH)
            time.sleep(0.5)  # LED on for half a second
            gpio.output(led_pin, gpio.LOW)
            time.sleep(0.5)  # LED off for half a second
    except Exception as e:
        log_message(f"Exception occurred in blink_led: {str(e)}")
        try:
            gpio.output(led_pin, gpio.LOW)
        except Exception:
            pass

# --- Systemd service control (no legacy fallback) ---
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

# Build a status-only payload to avoid overwriting web-configured settings with blanks
def build_status_payload(full_cfg):
    """
    Return only identity/runtime fields that should be updated from the device.
    Avoid sending configurable settings (call_sign, bands, grid, etc.).
    """
    keys = [
        "MAC_address",
        "hostname",
        "local_IP_address",
        "public_IP_address",
        "model_number",
        "serial_number",
        "uptime",
        "last_checkin",
        "setup_timestamp",
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

# Main function
def main():
    global gpio

    # Stop the WSPR process to release the transmit LED pin
    stop_wspr()
    time.sleep(1)  # give systemd a moment to release GPIO

    # Initialize GPIO for LED
    try:
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(led_pin, GPIO.OUT, initial=GPIO.LOW)
        gpio = GPIO  # ensure handle points to the real GPIO
    except Exception as e:
        log_message(f"GPIO init failed ({e}); continuing without LED.")
        class _NoGPIO:
            HIGH = 1
            LOW = 0
            def output(self,*a,**k): pass
            def cleanup(self): pass
        gpio = _NoGPIO()

    # Start LED blinking in a separate thread
    led_thread = threading.Thread(target=blink_led, daemon=True)
    led_thread.start()

    wspr_config = read_wspr_config()
    ensure_canonical_mac_in_config(wspr_config)

    # timezone-aware UTC
    wspr_config['setup_timestamp'] = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

    # Send status-only payload once (prevents overwriting web settings with blanks)
    status_payload = build_status_payload(wspr_config)
    server_response = send_data_to_server(status_payload, label="FIRST POST (status-only)")
    if server_response:
        write_wspr_config(wspr_config, server_response)

    # Poll until the deadline; write whenever the server response changes
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
        # sleep but don't overshoot too much if near deadline
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(POLL_INTERVAL, max(0.05, remaining)))
        i += 1

    # One final fetch just before restarting WSPR
    server_response = send_data_to_server(mac_only, label="FINAL FETCH")
    if server_response:
        write_wspr_config(wspr_config, server_response)

    # Start the WSPR process to reload any config file changes
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

# Handy systemctl reminders
#   sudo systemctl status  wspr-service
#   sudo systemctl start   wspr-service
#   sudo systemctl stop    wspr-service
#   sudo systemctl restart wspr-service

