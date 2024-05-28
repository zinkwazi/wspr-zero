import RPi.GPIO as GPIO
import requests
import json
import time
from datetime import datetime
import threading

# Define the URL of the remote server
server_url = "https://wspr-zero.com/setup/server-listener.php"
log_file = '/home/pi/wspr-zero/logs/setup-post.log'
led_pin = 18  # GPIO pin for WSPR-zero LED

# Function to read wspr-config.json
def read_wspr_config():
    with open('/home/pi/wspr-zero/wspr-config.json', 'r') as file:
        data = json.load(file)
    return data

# Function to write wspr-config.json
def write_wspr_config(existing_data, new_data):
    existing_data.update(new_data)
    with open('/home/pi/wspr-zero/wspr-config.json', 'w') as file:
        json.dump(existing_data, file, indent=4)

# Function to send data to the server
def send_data_to_server(data):
    try:
        headers = {'Content-Type': 'application/json'}
        log_message(f"Sending data to server: {json.dumps(data, indent=4)}")
        response = requests.post(server_url, headers=headers, json=data)
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
    with open(log_file, 'a') as file:
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
    except:
        GPIO.output(led_pin, GPIO.LOW)
        GPIO.cleanup()

# Main function
def main():
    # Initialize GPIO for LED
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(led_pin, GPIO.OUT)

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

    # Wait 5 seconds and then repeatedly request the config file 12 times without sending full config again
    for _ in range(12):
        server_response = send_data_to_server({'MAC_address': wspr_config['MAC_address']})
        if server_response:
            write_wspr_config(wspr_config, server_response)
        time.sleep(5)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    finally:
        GPIO.output(led_pin, GPIO.LOW)
        GPIO.cleanup()

