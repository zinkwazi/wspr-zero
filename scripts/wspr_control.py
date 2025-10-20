import json
import subprocess
import time
import signal
import sys
import os
import psutil

# Load configuration from JSON file
with open('/opt/wsprzero/wspr-zero/wspr-config.json') as config_file:
    config = json.load(config_file)

# Extract relevant data from the configuration
call_sign = config["call_sign"]
tx_band_frequencies = config["tx_band_frequency"]
rx_band_frequency = config["rx_band_frequency"]
transmit_or_receive = config["transmit_or_receive_option"]
grid_location = config["maidenhead_grid"]

def get_uptime():
    with open('/proc/uptime', 'r') as f:
        uptime_seconds = float(f.readline().split()[0])
    return uptime_seconds

def transmit():
    # Check system uptime
    uptime_seconds = get_uptime()

    # Delay to ensure everything is ready if uptime is under 2 minutes
    if uptime_seconds < 120:
        time.sleep(60)

    # Prepare the transmit command
    tx_command = [
        "sudo",
        "/opt/wsprzero/WsprryPi-zero/wspr",
        "-r",
        "-o",
        "-f",
        call_sign,
        grid_location,
        "23"
    ] + tx_band_frequencies

    # Log file for transmit
    tx_log_file = "/opt/wsprzero/wspr-zero/logs/wspr-transmit.log"

    # Execute the transmit command and redirect output to log file
    with open(tx_log_file, "a") as log_file:
        subprocess.Popen(tx_command, stdout=log_file, stderr=subprocess.STDOUT)

def receive():
    # Prepare the receive command
    rx_command = [
        "/opt/wsprzero/rtlsdr-wsprd/rtlsdr_wsprd",
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
    rx_log_file = "/opt/wsprzero/wspr-zero/logs/wspr-receive.log"
    # Execute the receive command and redirect output to log file
    with open(rx_log_file, "a") as log_file:
        subprocess.Popen(rx_command, stdout=log_file, stderr=subprocess.STDOUT)

def stop_processes():
    WSPR_BIN = "/opt/wsprzero/WsprryPi-zero/wspr"
    RTLSDR_BIN = "/opt/wsprzero/rtlsdr-wsprd/rtlsdr_wsprd"
    TARGET_BASENAMES = {"wspr", "rtlsdr_wsprd"}

    victims = []
    for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline']):
        try:
            cmd = proc.info.get('cmdline') or []
            exe = proc.info.get('exe') or ''
            base = os.path.basename(exe or (cmd[0] if cmd else ''))
            full0 = cmd[0] if cmd else ''

            is_target = (
                exe in (WSPR_BIN, RTLSDR_BIN) or
                base in TARGET_BASENAMES or
                full0 in (WSPR_BIN, RTLSDR_BIN)
            )

            # Also stop a sudo wrapper that launches our targets
            is_sudo_wrapper = (
                base == "sudo" and any(
                    "/WsprryPi-zero/wspr" in a or "rtlsdr_wsprd" in a
                    for a in cmd[1:]
                )
            )

            if is_target or is_sudo_wrapper:
                victims.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # Graceful then forceful
    for p in victims:
        try: p.terminate()
        except psutil.NoSuchProcess: pass
    gone, alive = psutil.wait_procs(victims, timeout=5)
    for p in alive:
        try: p.kill()
        except psutil.NoSuchProcess: pass

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

