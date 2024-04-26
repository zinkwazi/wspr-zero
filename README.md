sudo apt install rtl-sdr
sudo apt install librtlsdr-dev
sudo apt install libcurl4-openssl-dev
sudo apt install libfftw3-dev

Host mypi
    HostName example.com
    User pi
    IPQoS 0x00

add the following to the end of /etc/ssh/sshd_config
IPQoS 0x00


#2. Cloning the rtlsdr-wsprd repository and building it
git clone https://github.com/Guenael/rtlsdr-wsprd
cd rtlsdr-wsprd/
sudo make

#3. Turning of HDMI for less local EMI
/opt/vc/bin/tvservice -o


#4. As I experienced need a reboot here, my rtl-sdr dongle doesn't started else
sudo reboot

#5. Starting a new tmux terminal, after executing our wsprd command, we can detach and that runs smoothly in the background, even if we exit the SSH terminal
tmux


#6. Starting wsprd using RTL-SDR V3 dongle, set your call sign and locator first. -c stands fro callsign, -l for locator below:
./rtlsdr_wsprd -f 14.0956M -c WA0AAA -l JN97NN -d 2 -S


