#!/usr/bin/env python3
"""
WSPR-zero Battery Monitoring Script
Author: Greg Lawler
This script monitors the battery level and logs significant events related to battery status.
It can run with no parameters for production, or with a parameter to output battery stats to the console for testing.
"""

import struct
import smbus
import sys
import os
import time
from datetime import datetime

# Configuration Variables
BATTERY_SHUTDOWN_THRESHOLD = 10  # Set the battery percentage threshold for shutdown to 10%
LOGGING_THRESHOLD = BATTERY_SHUTDOWN_THRESHOLD + 5  # 15% upper bound for logging
LOG_FILE_PATH = "/var/log/wspr-battery.log"  # Log file path

def read_voltage(bus):
    """Returns the voltage from the Raspi UPS Hat via the provided SMBus object."""
    address = 0x36
    read = bus.read_word_data(address, 0x02)
    swapped = struct.unpack("<H", struct.pack(">H", read))[0]
    voltage = swapped * 1.25 / 1000 / 16
    return voltage

def read_capacity(bus):
    """Returns the remaining battery capacity as a percentage."""
    address = 0x36
    read = bus.read_word_data(address, 0x04)
    swapped = struct.unpack("<H", struct.pack(">H", read))[0]
    capacity = swapped / 256
    return capacity

def get_system_uptime():
    """Returns system uptime in seconds."""
    with open("/proc/uptime", 'r') as f:
        uptime_seconds = float(f.readline().split()[0])
        return uptime_seconds

def log_event(message):
    """Logs a message to the specified log file with a timestamp."""
    with open(LOG_FILE_PATH, "a") as log_file:
        log_file.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")

def main():
    """Main function to execute the battery and power checks."""
    bus = smbus.SMBus(1)  # Using I2C bus 1

    voltage = read_voltage(bus)
    capacity = read_capacity(bus)
    uptime = get_system_uptime()

    # If arguments are provided, print the battery stats to the console
    if len(sys.argv) > 1:
        print(f"Testing Mode: Battery Voltage: {voltage:.2f} V, Capacity: {capacity}%")
        print("This output is for testing purposes. Please run the script with no parameters in production.")
        return  # Exit after displaying the information

    # Log battery details if capacity is between the shutdown threshold and 5% above it
    if BATTERY_SHUTDOWN_THRESHOLD <= capacity <= LOGGING_THRESHOLD:
        log_event(f"Battery Voltage: {voltage:.2f} V")
        log_event(f"Battery Capacity: {capacity}%")

    # Check for shutdown condition
    if capacity < BATTERY_SHUTDOWN_THRESHOLD:
        if uptime < 1200:  # 20 minutes in seconds
            log_event(f"Battery below threshold ({capacity}%) but uptime ({uptime/60:.2f} minutes) under 20 minutes; skipping shutdown to let the battery charge.")
        else:
            log_event(f"Initiating shutdown due to low battery. Voltage: {voltage:.2f} V, Capacity: {capacity}%")
            os.system("sudo shutdown now")

if __name__ == "__main__":
    main()

