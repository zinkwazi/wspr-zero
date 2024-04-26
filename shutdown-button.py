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

# Variables to track button presses
button_presses = 0
last_press_time = 0
press_interval = 3  # Time interval in seconds to count multiple presses

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
    if GPIO.input(channel) == 0:  # Button pressed (falling edge)
        current_time = time.time()
        if current_time - last_press_time > press_interval:
            button_presses = 0  # Reset the count if the interval between presses is too long
        button_presses += 1
        last_press_time = current_time

        if button_presses == 5:
            logging.info("Button pressed 5 times in a row.")
            button_presses = 0  # Reset count after logging

    elif GPIO.input(channel) == 1:  # Button released (rising edge)
        # Check if button was pressed long enough for a shutdown
        if last_press_time and (time.time() - last_press_time >= 2) and button_presses == 1:
            logging.info("Button held for 2 seconds. Shutting down...")
            blink_led()  # Blink LED to indicate shutdown
            os.system("sudo shutdown now -h")
        last_press_time = 0  # Reset the last press time on release

# Setup event detection for both rising and falling edges
GPIO.add_event_detect(shutdown_pin, GPIO.BOTH, callback=button_callback, bouncetime=200)

# Main loop just waits indefinitely
try:
    logging.info("Monitoring for shutdown button press. Hold button for 2 seconds to shutdown or press 5 times for log.")
    while True:
        time.sleep(86400)  # Sleep for a day; effectively idle
except KeyboardInterrupt:
    logging.info("Program terminated by user")
finally:
    GPIO.cleanup()  # Clean up GPIO on normal exit

