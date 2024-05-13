import json
import socket
import os
import subprocess
import requests
from datetime import datetime
import time  # Import the time module

# Default configuration template
DEFAULT_CONFIG = {
    "MAC_address": "b8:27:eb:d0:4b:42",
    "IP_address": "192.168.5.151",
    "public_IP_address": "47.150.55.131",
    "time_on_pi": "Sun 12 May 19:50:47  2024",
    "model_number": "Raspberry Pi Zero W Rev 1.1",
    "serial_number": "000000001c851e17",
    "uptime": "18 hours, 50 minutes, 33 seconds",
    "RTC_module": True,
    "call_sign": "N0CALL",
    "band_frequency_1": 10,
    "band_frequency_2": 20,
    "band_frequency_3": 0,
    "transmit_or_receive_option": "transmit",
    "maidenhead_locator": "AA00aa"
}

def get_public_ip():
    try:
        ip = requests.get('https://api.ipify.org').text
    except requests.RequestException:
        ip = "Unable to fetch"
    return ip

def get_wireless_ip():
    try:
        process = subprocess.Popen(['ip', '-4', 'addr', 'show', 'wlan0', 'scope', 'global'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = process.communicate()
        ip = out.decode().split("inet ")[1].split("/")[0]
        return ip
    except:
        return "No IP Found"

def get_mac_address():
    try:
        process = subprocess.Popen(['cat', '/sys/class/net/wlan0/address'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        mac, err = process.communicate()
        return mac.decode().strip()
    except:
        return "No MAC Found"

def get_uptime():
    try:
        with open('/proc/uptime', 'r') as f:
            uptime_seconds = float(f.readline().split()[0])
            hours = int(uptime_seconds // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            seconds = int(uptime_seconds % 60)
            return f"{hours} hours, {minutes} minutes, {seconds} seconds"
    except:
        return "Unknown uptime"

def get_system_info():
    try:
        with open('/proc/device-tree/model', 'r') as f:
            model = f.readline().strip().replace('\x00', '')
    except FileNotFoundError:
        model = "Unknown Model"

    try:
        with open('/proc/cpuinfo', 'r') as f:
            lines = f.readlines()
            serial = [line for line in lines if "Serial" in line][0].split(":")[1].strip()
    except:
        serial = "Unknown Serial"

    return model, serial

def update_config():
    try:
        # Check if the configuration file exists, if not, create it with default values
        try:
            with open('../wspr-config.json', 'r') as file:
                config = json.load(file)
        except FileNotFoundError:
            config = DEFAULT_CONFIG  # Use default configuration if file not found

        # Update fields that are available from the local Pi
        config['MAC_address'] = get_mac_address()
        config['IP_address'] = get_wireless_ip()
        config['public_IP_address'] = get_public_ip()
        config['uptime'] = get_uptime()
        config['time_on_pi'] = datetime.now().strftime("%a %d %b %H:%M:%S %Z %Y")
        model, serial = get_system_info()
        config['model_number'] = model
        config['serial_number'] = serial

        # Save updated configuration
        with open('../wspr-config.json', 'w') as file:
            json.dump(config, file, indent=4)

        print("Configuration updated successfully.")

    except Exception as e:
        print(f"Failed to update configuration: {e}")

if __name__ == "__main__":
    time.sleep(30)  # Delay for 30 seconds before running the rest of the script
    update_config()
