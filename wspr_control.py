import json
import subprocess
import time

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
        subprocess.run(tx_command, stdout=log_file, stderr=subprocess.STDOUT)

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
        subprocess.run(rx_command, stdout=log_file, stderr=subprocess.STDOUT)

if __name__ == "__main__":
    if transmit_or_receive == "transmit":
        transmit()
    elif transmit_or_receive == "receive":
        receive()
    else:
        print("Invalid configuration: transmit_or_receive_option should be either 'transmit' or 'receive'.")
