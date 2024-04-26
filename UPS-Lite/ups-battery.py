#!/usr/bin/env python
import struct
import smbus
import sys
import os
import time
import RPi.GPIO as GPIO
from datetime import datetime

file_path = "ups-data.txt"

def readVoltage(bus):
        "This function returns as float the voltage from the Raspi UPS Hat via the provided SMBus object"
        address = 0x36
        read = bus.read_word_data(address, 0x02)
        swapped = struct.unpack("<H", struct.pack(">H", read))[0]
        voltage = swapped * 1.25 /1000/16
        return voltage

def readCapacity(bus):
        "This function returns as a float the remaining capacity of the battery"
        address = 0x36
        read = bus.read_word_data(address, 0x04)
        swapped = struct.unpack("<H", struct.pack(">H", read))[0]
        capacity = swapped / 256
        return capacity

def QuickStart(bus):
        address = 0x36
        bus.write_word_data(address, 0x06, 0x4000)

def PowerOnReset(bus):
        address = 0x36
        bus.write_word_data(address, 0xfe, 0x0054)

def output_battery(myList): # Write to the file
    f = open(file_path, "w")
    curr_dt = datetime.now()
    format = "%H:%M:%S %m-%d-%Y"
    f.write(curr_dt.strftime(format))
    f.write('\n')
    for element in myList:
         f.write(element)
         f.write('\n')
    f.close()

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(4, GPIO.IN)

bus = smbus.SMBus(1)  # 1 = /dev/i2c-1 (port I2C1)

PowerOnReset(bus)
QuickStart(bus)

time.sleep(2)
batteryVoltage = "Battery Voltage: %4.2f V" % readVoltage(bus)
batteryPercentage = "Battery Percentage: %i %%" % readCapacity(bus)

if readCapacity(bus) < 2:
	 os.system("sudo poweroff")

if readCapacity(bus) > 100:
	batteryPercentage = "Battery Percentage: 100%"

myList = [batteryVoltage, batteryPercentage]
time.sleep(10)
output_battery(myList)

