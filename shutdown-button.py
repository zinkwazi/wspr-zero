import RPi.GPIO as GPIO
import os
import time
import logging

# Setup logging
logging.basicConfig(filename='/var/log/wspr-zero-shutdown.log', level=logging.INFO, format='%(asctime)s %(message)s')

# Pin Definitions
shutdown_pin = 19  # GPIO pin for button, using BCM numbering
led_pin = 47       # GPIO pin for built-in LED, using BCM numbering

# Initialize GPIO
GPIO.setmode(GPIO.BCM)  # Use BCM pin numbering
GPIO.setwarnings(False)  # Disable runtime warnings to avoid unnecessary output
GPIO.setup(shutdown_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Button to ground with a pull-up resistor
GPIO.setup(led_pin, GPIO.OUT)  # LED as output

# Timestamp to track when button was pressed
button_pressed_time = None

def blink_led():
    """Function to blink the LED rapidly to indicate shutdown."""
    for _ in range(20):  # Increase the number of blinks
        GPIO.output(led_pin, True)
        time.sleep(0.1)  # Decrease sleep time to blink faster
        GPIO.output(led_pin, False)
        time.sleep(0.1)

def button_callback(channel):
    """Callback function to handle button events."""
    global button_pressed_time
    current_state = GPIO.input(channel)
    if current_state == 0:  # Button pressed (falling edge)
        button_pressed_time = time.time()
        logging.info("Button pressed. Waiting to confirm duration...")
    else:  # Button released (rising edge)
        if button_pressed_time is None:
            return
        elapsed = time.time() - button_pressed_time
        if elapsed >= 2:  # Reduced the required hold time to 2 seconds
            logging.info("Button held for 2 seconds. Shutting down...")
            blink_led()  # Blink LED to indicate shutdown
            os.system("sudo shutdown now -h")
        else:
            logging.info("Button was not held long enough. No action taken.")
        button_pressed_time = None

# Setup event detection for both rising and falling edges
GPIO.add_event_detect(shutdown_pin, GPIO.BOTH, callback=button_callback, bouncetime=500)

# Main loop just waits indefinitely
try:
    logging.info("Monitoring for shutdown button press. Hold button for 2 seconds to shutdown.")
    while True:
        time.sleep(86400)  # Sleep for a day; effectively idle
except KeyboardInterrupt:
    logging.info("Program terminated by user")
finally:
    GPIO.cleanup()  # Clean up GPIO on normal exit

