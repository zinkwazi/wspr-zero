import RPi.GPIO as GPIO
import requests
import json
import time
from datetime import datetime
import threading
import subprocess
import pwd
import os
import getpass

# GPIO pin for WSPR-zero LED
led_pin = 18

# Define the URL of the remote server
server_url = "https://wspr-zero.com/ez-config/server-listener.php"

# Resolve the target user for log ownership:
# - Prefer current effective user
# - You can override with env WSPR_LOG_USER if you ever need to
target_user = os.environ.get("WSPR_LOG_USER", getpass.getuser())
try:
    pw = pwd.getpwnam(target_user)
    uid, gid = pw.pw_uid, pw.pw_gid
except KeyError:
    uid, gid = os.geteuid(), os.getegid()   # fallback

def safe_chown(path, uid, gid):
    try:
        os.chown(path, uid, gid)
    except PermissionError:
        # Non-root users can't chown; that's fine — just continue
        pass

def safe_chmod(path, mode):
    try:
        os.chmod(path, mode)
    except PermissionError:
        pass

# Set up log directory and log file
log_dir = '/opt/wsprzero/wspr-zero/logs'
log_file = os.path.join(log_dir, 'setup-post.log')

# Create log directory if it doesn't exist
os.makedirs(log_dir, exist_ok=True)
safe_chown(log_dir, uid, gid)
# setgid bit so files inherit the directory's group when created by root later
safe_chmod(log_dir, 0o2775)

# Create log file if it doesn't exist
if not os.path.exists(log_file):
    open(log_file, 'a').close()
safe_chown(log_file, uid, gid)
safe_chmod(log_file, 0o664)

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
        # 5s connect, 15s read timeout
        response = requests.post(server_url, headers=headers, json=data, timeout=(3, 7))
        if response.status_code == 200:
            return response.json()
        else:
            log_message(f"Failed to send data. Status code: {response.status_code}, Response: {response.text}")
            return None
    except Exception as e:
        log_message(f"Exception occurred while sending data: {str(e)}")
        return None

# Function to log messages to a file
def log_message(message):
    with open(log_file, 'a') as file:
        file.write(message + '\n')
        file.write('-' * 50 + '\n')

# Function to blink the LED
def blink_led():
    try:
        while True:
            for _ in range(5):  # Rapid blink 5 times a second
                GPIO.output(led_pin, GPIO.HIGH)
                time.sleep(0.1)
                GPIO.output(led_pin, GPIO.LOW)
                time.sleep(0.1)
            GPIO.output(led_pin, GPIO.HIGH)
            time.sleep(0.5)  # LED on for half a second
            GPIO.output(led_pin, GPIO.LOW)
            time.sleep(0.5)  # LED off for half a second
    except Exception as e:
        log_message(f"Exception occurred in blink_led: {str(e)}")
        try:
            GPIO.output(led_pin, GPIO.LOW)
        except Exception:
            pass

# Function to stop the WSPR process
def stop_wspr():
    log_message("Stopping WSPR process")
    cmd = ['/usr/bin/python3', '/opt/wsprzero/wspr-zero/scripts/wspr_control.py', 'stop']

# Function to start the WSPR process
def start_wspr():
    log_message("Starting WSPR process")
    cmd = ['/usr/bin/python3', '/opt/wsprzero/wspr-zero/scripts/wspr_control.py', 'start']

# Require root so GPIO/LED always works
if os.geteuid() != 0:
    log_message("server_checkin.py must run as root for GPIO access; aborting.")
    raise SystemExit("Run with sudo or via wspr-server-checkin.service (User=root).")

# Main function
def main():
    # Stop the WSPR process to release the transmit LED pin
    stop_wspr()

    # Initialize GPIO for LED
    try:
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(led_pin, GPIO.OUT, initial=GPIO.LOW)
    except Exception as e:
        log_message(f"GPIO init failed ({e}); continuing without LED.")
        class _NoGPIO:
            def output(self,*a,**k): pass
            def cleanup(self): pass
        GPIO = _NoGPIO()

    # Start LED blinking in a separate thread
    led_thread = threading.Thread(target=blink_led)
    led_thread.daemon = True
    led_thread.start()

    wspr_config = read_wspr_config()
    wspr_config['setup_timestamp'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

    # Send the full configuration to the server once
    server_response = send_data_to_server(wspr_config)

    if server_response:
        write_wspr_config(wspr_config, server_response)

    # Wait 5 seconds and then repeatedly request the config file 10 times without sending full config again
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
            GPIO.output(led_pin, GPIO.LOW)
            GPIO.cleanup()
        except Exception:
            pass

