import RPi.GPIO as GPIO
import os
import time
import logging

# Delay start
time.sleep(30)  # Delay 30 seconds

# Ensure the log directory exists
log_dir = '/home/pi/wspr-zero/logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# Setup logging
logging.basicConfig(filename='/home/pi/wspr-zero/logs/wspr-zero-shutdown.log', level=logging.INFO, format='%(asctime)s %(message)s')

# Pin Definitions
shutdown_pin = 19  # GPIO pin for button
led_pin = 18       # GPIO pin for WSPR-zero LED

# Initialize GPIO
GPIO.setmode(GPIO.BCM)  # Use BCM pin numbering
GPIO.setwarnings(False)  # Disable runtime warnings to avoid unnecessary output
GPIO.setup(shutdown_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Button to ground with a pull-up resistor
GPIO.setup(led_pin, GPIO.OUT)  # LED as output

# Variables to track button presses
button_presses = 0
last_press_time = 0
press_interval = 10  # Time interval in seconds to count multiple presses (increased to 10 seconds)
hold_time = 8  # Time in seconds to hold the button for shutdown

def blink_led():
    """Function to blink the LED rapidly to indicate shutdown."""
    for _ in range(20):  # Increase the number of blinks
        GPIO.output(led_pin, True)
        time.sleep(0.1)  # Decrease sleep time to blink faster
        GPIO.output(led_pin, False)
        time.sleep(0.1)

def button_callback(channel):
    """Callback function to handle button events."""
    global button_presses, last_press_time
    current_time = time.time()
    if GPIO.input(channel) == 0:  # Button pressed (falling edge)
        if current_time - last_press_time > press_interval:
            button_presses = 0  # Reset count if interval between presses exceeds press_interval
        button_presses += 1
        last_press_time = current_time

        if button_presses == 5:
            logging.info("Button pressed 5 times in a row. Entering Setup Mode.")
            os.system("python3 /home/pi/wspr-zero/scripts/server_checkin.py")
            button_presses = 0  # Reset count after sending data

    elif GPIO.input(channel) == 1:  # Button released (rising edge)
        if last_press_time and (current_time - last_press_time >= hold_time) and button_presses == 1:
            logging.info("Button held for 10 seconds. Shutting down...")
            blink_led()  # Blink LED to indicate shutdown
            os.system("sudo shutdown now -h")
        last_press_time = 0  # Reset the last press time on release

# Setup event detection for both rising and falling edges
GPIO.add_event_detect(shutdown_pin, GPIO.BOTH, callback=button_callback, bouncetime=200)

# Main loop just waits indefinitely
try:
    logging.info("Monitoring utility button. Hold for 10 seconds to shutdown or press 5 times to post data.")
    while True:
        time.sleep(86400)  # Sleep for a day; effectively idle
except KeyboardInterrupt:
    logging.info("Program terminated by user")
finally:
    GPIO.cleanup()  # Clean up GPIO on normal exit
