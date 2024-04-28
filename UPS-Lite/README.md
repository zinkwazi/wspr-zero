# WSPR-zero UPS-Lite Battery Monitoring Script

- This script is designed to monitor the battery level of a UPS-Lite battery attached to a Raspberry Pi running the WSPR-zero project. 
- The script logs significant battery status events and automatically shuts down the system to prevent damage due to low battery voltage.

## Features

- **Voltage Monitoring**: Measures and logs the battery voltage.
- **Capacity Monitoring**: Tracks the remaining battery capacity and logs it when it falls within certain thresholds.
- **Automatic Shutdown**: Safely shuts down the Raspberry Pi if the battery capacity falls below a critical threshold and the system has been running for at least 20 minutes.
- **Event Logging**: All significant battery events are logged with timestamps for later review.

## Hardware Requirements

- Raspberry Pi (any model that supports I2C)
- UPS-Lite Battery Module attached to the Raspberry Pi

## Setup and Configuration

### Installation

1. **Connect the UPS-Lite**: Ensure your UPS-Lite is properly connected to your Raspberry Pi via the GPIO pins.
2. **Enable I2C on Raspberry Pi**:
    - Run `sudo raspi-config`.
    - Navigate to `Interfacing Options`.
    - Select `I2C` and enable it.
    - Reboot your Pi.

### Script Deployment

- **Set Permissions**: Make sure the script is executable:
    ```bash
    chmod +x ~/wspr-zero/UPS-Lite/wspr-battery.py
    ```

## Usage

### Running the Script

- **Manual Execution**: To manually run the script and see the battery status in real-time:
    ```bash
    python3 ~/wspr-zero/UPS-Lite/wspr-battery.py test
    ```
- **Automated Monitoring**: Configure the script to run automatically every 10 minutes to monitor the battery status silently.

### Configuring Crontab

To ensure the script runs every 10 minutes, add it to the crontab with the following steps:

1. Open your crontab:
    ```bash
    crontab -e
    ```
2. Add the following line to schedule the script to run at 10-minute intervals:
    ```crontab
    */10 * * * * sudo python3 /home/pi/wspr-zero/UPS-Lite/wspr-battery.py >> /home/pi/wspr-zero/UPS-Lite/battery.log 2>&1
    ```
3. Save and exit the editor. The cron job will now execute the script every 10 minutes.

## Logs

- **Log File**: The battery events and statuses are logged to `/var/log/wspr-battery.log`.
- You can view the log file by running:
    ```bash
    cat /var/log/wspr-battery.log
    ```


