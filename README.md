![WSPR-zero Logo](images/WSPR-zero-logo-medium.png)

# WSPR-zero Project

WSPR-zero provides the components for a cost-effective and ultra-portable Raspberry Pi Zero solution for transmitting and receiving WSPR signals.
The project brings together various community contributions into an easy-to-install package tailored for the Raspberry Pi Zero, although it is also tested on the Raspberry Pi 3 & 4.

Designed for portability and low power requirements, this project is perfectly suited for outdoor activities such as backpacking and traveling.

Enjoy!

-- Greg Lawler, K6FTP

## Download WSPR-zero

Download the latest version here: [wspr-zero.com/downloads](https://wspr-zero.com/downloads)

Visit [wspr-zero.com](https://wspr-zero.com) for more details.

## About WSPR

**WSPR** (pronounced "whisper") stands for Weak Signal Propagation Reporter. 
WSPR is a digital radio protocol to transmit low-power shortwave signals globally, testing radio wave propagation by bouncing off the ionosphere. 

Each WSPR transmission is 110.6 seconds long. This precise duration allows for a slow data rate that enhances the likelihood of reception under weak signal conditions. The remaining time within the two-minute interval (about 9.4 seconds) is used as a buffer to ensure that transmissions do not overlap and that there is time for transceivers to switch from transmit to receive mode, and vice versa.

Adding to the fun, every WSPR transmission ever sent or received—is logged to a massive database and is available for download, providing a great dataset for budding data analysts!

**Fun Fact:** Each WSPR transmission contains just 40.5 bytes of data at the impressively low data rate of 1.46 baud!

### Requirements

- Raspberry Pi Zero, Pi 3 or Pi 4
- WSPR-zero or TAPR.org Raspberry Pi low pass filter hat for WSPR transmission
- RTL-SDR USB device for receiving WSPR signals
- HDMI dummy load dongle (prevents crashing upon transmission on Raspberry Pi Zero)
- Antenna of some sort. Simple half dipole wire antenna is easy, cheap and works great!
- Optional: UPS-Lite backup battery board for automated graceful shutdown when external power is lost 

### Raspberry Pi Zero with WSPR-zero Hat
![WSPR-zero in action](images/IMG_9521.jpg "WSPR-zero in Action")
*Close-up view of a Raspberry Pi Zero 2 W, WSPR-zero Hat and UPS-Lite.*

### Features

- **Compatibility**: Primarily developed for the Pi Zero but also works on Pi 3 & 4.
- **Cost-Effective**: The total cost of the setup ranges from $40 - $80, depending on the antenna used.
- **WSPR-zero Filter Hat**: Developed by Outside Open, based on a filter by TAPR (tapr.org), but redesigned to comply with standard Raspberry Pi HAT specifications. This board helps filter out the noisy RF generated by the Pi.
- **Transmission Modes**: Includes both transmit and receive modes.
  - **Transmit**: Requires a WSPR-zero or TAPR Reapberry Pi hat.
  - **Receive**: Requires an RTL-SDR USB device.
- **Extended Run Time**: Can easily run for over 24 hours on a portable phone battery pack.

### Coming in V2
- **Real Time Clock I2C Headers:**
WSPR relies heavily on accurate time synchronization. Transmitters and receivers must have their clocks synchronized to Universal Time Coordinated (UTC) to within a second or so. This synchronization is critical because slight timing offsets can lead to missed transmissions or failure to decode signals properly.
- **Install Scripts:**
Scripts to help newcomers get started with minimal effort.

## Installation
No install script yet - pull the repo and go from there :)

Ensure your Raspberry Pi is up to date and connected to the internet before starting the installation.
```
sudo apt update && sudo apt upgrade
sudo apt install rtl-sdr librtlsdr-dev libcurl4-openssl-dev libfftw3-dev
```
### SSH Configuration
**Add IPQoS to sshd_config**: If SSH access is painfully slow, run the following command on the Pi
```
echo "IPQoS 0x00" | sudo tee -a /etc/ssh/sshd_config
```

## Contributing

Contributions to the WSPR-zero project are welcome! Please refer to the issues tab on GitHub to find tasks that need help or submit your suggestions and contributions via pull requests.

## Licensing

- This project is licensed under the MIT License.
- All WSPR transmissions require the operator to be licensed by the FCC (or similar entitiy in other countries) in order to legally transmit.
- No license is required to use WSPR-zero as a WSPR receiver.

## Acknowledgments

Thanks to all contributors from the ham radio community, especially those who have provided testing, feedback and code improvements.

## Support and Documentation

For more details, visit the [official GitHub repository](https://github.com/zinkwazi/wspr-zero).

## Images

### WSPR-zero in Action
![WSPR-zero board close-up](images/IMG_9264.jpg "WSPR-zero Board Mobile with Battery")
*Ready to hit the road.*

### WSPR-zero Utility Button
![WSPR-zero additional setup](images/IMG_9275.jpg "WSPR-zero Button")
*Utility Button to gracefully shut down the Pi if held for 10 seconds or post internal IP info if pressed 5 times.*

### WSPR-zero Utility Button Log
![WSPR-zero additional setup](images/Screenshot-utility-button-log.png "WSPR-zero log")
*Utility Button log file showing the two use cases.*

### wsprnet.org 12 hour map for K6FTP
![WSPR-zero additional setup](images/Screenshot-map.png "WSPR-zero map")
*Screenshot from wsprnet.org for traffic from a WSPR-zero using a $4 half dipole 30m wire antenna draped on a hedge.*

### WSPR-zero v2 Board Render
![WSPR-zero additional setup](images/WSPR-zero-v2.jpg "WSPR-zero map")
*Render of v2 of the WSPR-zero Hat with RTC header - coming soon.**


**WSPR-zero Project by 2024 Greg Lawler.** Visit the [GitHub repository](https://github.com/zinkwazi/wspr-zero) for more information.
