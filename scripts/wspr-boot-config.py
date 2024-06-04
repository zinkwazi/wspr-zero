import json
import subprocess
from datetime import datetime
import time

# Default configuration template
DEFAULT_CONFIG = {
    "hostname": "",
    "MAC_address": "",
    "local_IP_address": "",
    "public_IP_address": "",
    "model_number": "",
    "serial_number": "",
    "uptime": "",
    "last_checkin": "",
    "RTC_module": "",
    "call_sign": "",
    "rx_band_frequency": "30m",
    "tx_band_frequency": [
        "30m",
        "0",
        "30m",
        "0"
    ],
    "transmit_or_receive_option": "",
    "maidenhead_grid": "",
    "setup_timestamp": ""
}

def get_wireless_ip():
    try:
        process = subprocess.Popen(['hostname', '-I'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = process.communicate()
        ip = out.decode().strip().split()[0]
        return ip
    except:
        return "No IP Found"

def get_mac_address():
    try:
        with open('/sys/class/net/wlan0/address', 'r') as f:
            return f.readline().strip()
    except:
        return "No MAC Found"

def get_uptime():
    try:
        with open('/proc/uptime', 'r') as f:
            uptime_seconds = float(f.readline().split()[0])
            hours = int(uptime_seconds // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            seconds = int(uptime_seconds % 60)
            return f"{hours} hours, {minutes} minutes, {seconds} seconds", uptime_seconds
    except:
        return "Unknown uptime", 0

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

def get_hostname():
    try:
        with open('/etc/hostname', 'r') as f:
            hostname = f.readline().strip()
        return hostname
    except:
        return "Unknown Hostname"

def update_config():
    try:
        # Check if the configuration file exists, if not, create it with default values
        try:
            with open('/home/pi/wspr-zero/wspr-config.json', 'r') as file:
                config = json.load(file)
        except FileNotFoundError:
            config = DEFAULT_CONFIG.copy()  # Use default configuration if file not found

        # Update fields that are available from the local Pi
        config['hostname'] = get_hostname()
        config['MAC_address'] = get_mac_address()
        config['local_IP_address'] = get_wireless_ip()
        config['uptime'], uptime_seconds = get_uptime()
        model, serial = get_system_info()
        config['model_number'] = model
        config['serial_number'] = serial

        # Save updated configuration
        with open('/home/pi/wspr-zero/wspr-config.json', 'w') as file:
            json.dump(config, file, indent=4)

        print("Configuration updated successfully.")

    except Exception as e:
        print(f"Failed to update configuration: {e}")

if __name__ == "__main__":
    uptime_info, uptime_seconds = get_uptime()
    if uptime_seconds < 60:
        time.sleep(30)  # Delay for 30 seconds if uptime is under 1 minute
    update_config()

