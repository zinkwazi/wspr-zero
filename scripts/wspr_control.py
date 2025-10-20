#!/usr/bin/env python3
import json
import subprocess
import time
import signal
import sys
import os
import psutil

# --- Paths / constants ---
CONFIG_PATH = '/opt/wsprzero/wspr-zero/wspr-config.json'
LOG_DIR = '/opt/wsprzero/wspr-zero/logs'
WSPR_BIN = '/opt/wsprzero/WsprryPi-zero/wspr'
RTLSDR_BIN = '/opt/wsprzero/rtlsdr-wsprd/rtlsdr_wsprd'

# --- Old behavior: load config once for start/stop flows (unchanged) ---
with open(CONFIG_PATH) as config_file:
    config = json.load(config_file)

# Extract relevant data from the configuration (unchanged)
call_sign = config["call_sign"]
tx_band_frequencies = config["tx_band_frequency"]
rx_band_frequency = config["rx_band_frequency"]
transmit_or_receive = config["transmit_or_receive_option"]
grid_location = config["maidenhead_grid"]

def get_uptime():
    with open('/proc/uptime', 'r') as f:
        uptime_seconds = float(f.readline().split()[0])
    return uptime_seconds

# -------- Original behaviors (unchanged) --------
def transmit():
    # TX-only delay like before
    uptime_seconds = get_uptime()
    if uptime_seconds < 120:
        time.sleep(60)

    tx_command = [
        "sudo",                 # preserved
        WSPR_BIN,
        "-r", "-o", "-f",       # preserved (skip NTP per your workflow)
        call_sign,
        grid_location,
        "23"
    ] + tx_band_frequencies

    tx_log_file = os.path.join(LOG_DIR, "wspr-transmit.log")
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(tx_log_file, "a") as log_file:
        subprocess.Popen(tx_command, stdout=log_file, stderr=subprocess.STDOUT)

def receive():
    rx_command = [
        RTLSDR_BIN,
        "-f", rx_band_frequency,
        "-c", call_sign,
        "-l", grid_location,
        "-d", "2",
        "-S"
    ]
    rx_log_file = os.path.join(LOG_DIR, "wspr-receive.log")
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(rx_log_file, "a") as log_file:
        subprocess.Popen(rx_command, stdout=log_file, stderr=subprocess.STDOUT)

def stop_processes():
    # Your safe killer (unchanged semantics)
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

            # Also stop a sudo wrapper that launches our targets (unchanged)
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

    # Graceful then forceful (unchanged)
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

# -------- New: supervised run mode (additive only) --------
stop_flag = False
reload_flag = False

def load_config_fresh():
    with open(CONFIG_PATH) as f:
        return json.load(f)

def start_child_from(cfg):
    tor = (cfg.get("transmit_or_receive_option") or "").strip().lower()
    os.makedirs(LOG_DIR, exist_ok=True)

    if tor == "transmit":
        # Preserve TX-only boot delay here too
        if get_uptime() < 120:
            time.sleep(60)

        cmd = ["sudo", WSPR_BIN, "-r", "-o", "-f", cfg["call_sign"], cfg["maidenhead_grid"], "23"] \
              + list(cfg["tx_band_frequency"])
        log_path = os.path.join(LOG_DIR, "wspr-transmit.log")
    elif tor == "receive":
        cmd = [RTLSDR_BIN, "-f", cfg["rx_band_frequency"], "-c", cfg["call_sign"], "-l",
               cfg["maidenhead_grid"], "-d", "2", "-S"]
        log_path = os.path.join(LOG_DIR, "wspr-receive.log")
    else:
        print("Invalid configuration: transmit_or_receive_option should be 'transmit' or 'receive'.", flush=True)
        sys.exit(2)

    log_file = open(log_path, "a")
    return subprocess.Popen(cmd, stdout=log_file, stderr=subprocess.STDOUT)

def sigterm(_sig, _frm):
    global stop_flag; stop_flag = True

def sighup(_sig, _frm):
    global reload_flag; reload_flag = True

def run_supervisor():
    signal.signal(signal.SIGTERM, sigterm)
    signal.signal(signal.SIGINT, sigterm)
    signal.signal(signal.SIGHUP, sighup)

    backoff = 5
    while not stop_flag:
        cfg = load_config_fresh()
        child = start_child_from(cfg)

        # wait until child exits or we get a signal
        while child.poll() is None and not stop_flag and not reload_flag:
            time.sleep(1)

        if stop_flag:
            stop_processes()
            break

        if reload_flag:
            reload_flag = False
            stop_processes()
            backoff = 5
            continue  # immediate restart with new config

        # child ended unexpectedly → restart with backoff (cap 60s)
        time.sleep(backoff)
        backoff = min(backoff * 2, 60)

# -------- CLI entrypoint (start/stop unchanged; run added) --------
if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ["start", "stop", "run"]:
        print("Usage: python wspr_control.py <start|stop|run>")
        sys.exit(1)

    # Original handlers for start/stop (unchanged)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if sys.argv[1] == "start":
        if transmit_or_receive == "transmit":
            transmit()
        elif transmit_or_receive == "receive":
            receive()
        else:
            print("Invalid configuration: transmit_or_receive_option should be either 'transmit' or 'receive'.")
        sys.exit(0)

    if sys.argv[1] == "stop":
        stop_processes()
        sys.exit(0)

    if sys.argv[1] == "run":
        # New supervised mode (additive)
        run_supervisor()
        sys.exit(0)

