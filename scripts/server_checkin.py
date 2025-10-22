#!/usr/bin/env python3
import RPi.GPIO as GPIO
import requests
import json
import time
from datetime import datetime
import threading
import subprocess
import os
import shutil

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

def safe_chown(path, uid, gid):
    try:
        os.chown(path, uid, gid)
    except PermissionError:
        pass
    except FileNotFoundError:
        pass

def safe_chmod(path, mode):
    try:
        os.chmod(path, mode)
    except PermissionError:
        pass
    except FileNotFoundError:
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

# Function to read wspr-config.json
def read_wspr_config():
    with open('/opt/wsprzero/wspr-zero/wspr-config.json', 'r') as file:
        data = json.load(file)
    return data

# Function to write wspr-config.json
def write_wspr_config(existing_data, new_data):
    existing_data.update(new_data)
    with open('/opt/wsprzero/wspr-zero/wspr-config.json', 'w') as file:
        json.dump(existing_data, file, indent=4)

# Function to send data to the server
def send_data_to_server(data):
    try:
        headers = {'Content-Type': 'application/json'}
        log_message(f"Sending data to server: {json.dumps(data, indent=4)}")
        # 3s connect, 7s read timeout
        response = requests.post(server_url, headers=headers, json=data, timeout=(3, 7))
        if response.status_code == 200:
            return response.json()
        else:
            log_message(f"Failed to send data. Status code: {response.status_code}, Response: {response.text}")
            return None
    except Exception as e:
        log_message(f"Exception occurred while sending data: {str(e)}")
        return None

# ===== GPIO handling =====
# Use a handle we can safely replace if init fails
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
    """
    Run systemctl <action> <SERVICE_NAME>, log stdout/stderr, and return True/False.
    """
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

# Main function
def main():
    global gpio

    # Stop the WSPR process to release the transmit LED pin
    stop_wspr()

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
    wspr_config['setup_timestamp'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

    # Send the full configuration to the server once
    server_response = send_data_to_server(wspr_config)
    if server_response:
        write_wspr_config(wspr_config, server_response)

    # Repeat 5 times requesting updates by MAC only (3s between attempts)
    for _ in range(5):
        server_response = send_data_to_server({'MAC_address': wspr_config['MAC_address']})
        if server_response:
            write_wspr_config(wspr_config, server_response)
        time.sleep(3)

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

