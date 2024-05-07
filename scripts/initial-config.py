import json
import os
import netifaces
import requests
from time import sleep

# Sleep for 30 seconds to ensure the network is up
sleep(30)

# Function to get the MAC address from a specific network interface
def get_mac_address(interface):
    try:
        return netifaces.ifaddresses(interface)[netifaces.AF_LINK][0]['addr']
    except KeyError:
        return ""

# Function to get the local IPv4 address from a specific network interface
def get_local_ipv4(interface):
    try:
        return netifaces.ifaddresses(interface)[netifaces.AF_INET][0]['addr']
    except KeyError:
        return ""

# Function to get the public IPv4 address
def get_public_ipv4():
    try:
        return requests.get('https://api.ipify.org').text
    except Exception:
        return ""

# Function to get the system uptime
def get_uptime():
    try:
        with open('/proc/uptime', 'r') as f:
            return float(f.readline().split()[0])
    except Exception:
        return ""

# Load existing data from wspr-config.json, if it exists
config_file = os.path.expanduser('~pi/wspr-zero/wspr-config.json')
if os.path.exists(config_file):
    with open(config_file, 'r') as f:
        config = json.load(f)
else:
    config = {}

# Update the configuration with the new values
config['callsign'] = config.get('callsign', '')
config['ethernet'] = {
    'mac_address': get_mac_address('eth0'),
    'local_ipv4': get_local_ipv4('eth0')
}
config['wifi'] = {
    'mac_address': get_mac_address('wlan0'),
    'local_ipv4': get_local_ipv4('wlan0')
}
config['public_ipv4'] = get_public_ipv4()
config['uptime'] = get_uptime()
config['band'] = config.get('band', '')
config['rtc_clock'] = config.get('rtc_clock', '')

# Write updated data back to the JSON file
with open(config_file, 'w') as f:
    json.dump(config, f, indent=4)

print(f"{config_file} has been updated.")
