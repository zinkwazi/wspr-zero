import json
import subprocess
import time
import signal
import sys
import os
import psutil

# Load configuration from JSON file
with open('/home/pi/wspr-zero/wspr-config.json') as config_file:
    config = json.load(config_file)

# Extract relevant data from the configuration
call_sign = config["call_sign"]
tx_band_frequencies = config["tx_band_frequency"]
rx_band_frequency = config["rx_band_frequency"]
transmit_or_receive = config["transmit_or_receive_option"]
grid_location = config["maidenhead_grid"]

def transmit():
    # Delay to ensure everything is ready
    time.sleep(60)
    # Prepare the transmit command
    tx_command = [
        "sudo",
        "/home/pi/wspr-zero/WsprryPi/wspr",
        "-r",
        "-o",
        "-f",
        call_sign,
        grid_location,
        "23"
    ] + tx_band_frequencies
    # Log file for transmit
    tx_log_file = "/home/pi/wspr-zero/logs/wspr-transmit.log"
    # Execute the transmit command and redirect output to log file
    with open(tx_log_file, "a") as log_file:
        subprocess.Popen(tx_command, stdout=log_file, stderr=subprocess.STDOUT)

def receive():
    # Prepare the receive command
    rx_command = [
        "/home/pi/wspr-zero/rtlsdr-wsprd/rtlsdr_wsprd",
        "-f",
        rx_band_frequency,
        "-c",
        call_sign,
        "-l",
        grid_location,
        "-d",
        "2",
        "-S"
    ]
    # Log file for receive
    rx_log_file = "/home/pi/wspr-zero/logs/wspr-receive.log"
    # Execute the receive command and redirect output to log file
    with open(rx_log_file, "a") as log_file:
        subprocess.Popen(rx_command, stdout=log_file, stderr=subprocess.STDOUT)

def stop_processes():
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        if proc.info['cmdline'] and ('wspr' in proc.info['cmdline'][0] or 'rtlsdr_wsprd' in proc.info['cmdline'][0]):
            print(f"Stopping process {proc.info['pid']}: {proc.info['cmdline']}")
            try:
                proc.terminate()
                proc.wait()
            except psutil.AccessDenied:
                print(f"Access denied when trying to stop process {proc.info['pid']}, trying with sudo.")
                subprocess.run(['sudo', 'kill', '-TERM', str(proc.info['pid'])])

def signal_handler(sig, frame):
    print('Stopping processes...')
    stop_processes()
    print('Processes stopped. Exiting.')
    sys.exit(0)

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ["start", "stop"]:
        print("Usage: python wspr_control.py <start|stop>")
        sys.exit(1)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if sys.argv[1] == "start":
        if transmit_or_receive == "transmit":
            transmit()
        elif transmit_or_receive == "receive":
            receive()
        else:
            print("Invalid configuration: transmit_or_receive_option should be either 'transmit' or 'receive'.")
        # Exit immediately to return control to the command line
        sys.exit(0)
    elif sys.argv[1] == "stop":
        stop_processes()
        sys.exit(0)
