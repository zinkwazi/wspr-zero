#!/bin/bash

# Check if script is run as root
if [ "$EUID" -ne 0 ]
  then echo "Please run as root"
  exit
fi

# Prompt user to agree
read -p "WARNING: This script will reset all settings on this pi. Are you sure you want to continue? (yes/no): " choice
case "$choice" in
  yes|YES|Yes)
    echo "Starting reset..."
    ;;
  *)
    echo "Reset cancelled."
    exit
    ;;
esac

# Clean up apt cache
apt-get clean
apt-get autoremove -y

# Remove log files
rm -rf /var/log/*
rm -rf /tmp/*

# Reset WSPR
rm /home/pi/wspr-zero/logs/*
rm /home/pi/wspr-zero/wspr-config.json

# Clear bash history for all users
sh -c 'cat /dev/null > ~/.bash_history && history -c'
for user in $(ls /home); do
    sh -c "cat /dev/null > /home/$user/.bash_history && history -c"
done

# Remove specific user history files if they exist
rm -f /root/.bash_history
for user in $(ls /home); do
    rm -f /home/$user/.bash_history
done

# Clear DHCP leases
rm -f /var/lib/dhcp/*

# Clear udev rules (to avoid issues with network interfaces)
rm -f /etc/udev/rules.d/70-persistent-net.rules
rm -f /lib/udev/rules.d/75-persistent-net-generator.rules

# Clear temporary files
rm -rf /tmp/*
rm -rf /var/tmp/*

# Clear user-specific stuff
for user in $(ls /home); do
    rm -rf /home/$user/.cache/*
    rm -rf /home/$user/.ssh/*
done
rm -rf /root/.cache/*

# Clear machine ID (to regenerate on next boot)
truncate -s 0 /etc/machine-id

# Clear shell history
history -c
sh -c 'history -c'

# Reset WiFi to default
bash -c 'cat << EOF > /etc/wpa_supplicant/wpa_supplicant.conf
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
EOF'

# Remove dev playground directory and contents
rm -rf ~pi/dev

# Short delay
echo "Cleanup complete. The system will halt in 10 seconds."
sleep 10

# Halt the system
halt

