#!/bin/bash
# reset-img.sh — sanitize and reset a WSPR-zero Raspberry Pi image before re-imaging or hand-off
#
# WHAT IT DOES
#   - Confirms intent, requires root, and runs with strict bash options
#   - Cleans apt caches, temp files, logs (keeps log directories), and DHCP leases
#   - Resets WSPR-zero state (logs + wspr-config.json) if present
#   - Clears user caches, SSH keys (per-user), and shell histories (by removing files)
#   - Resets machine identity so the next boot generates new IDs
#   - Writes a minimal /etc/wpa_supplicant/wpa_supplicant.conf with safe permissions
#   - Powers off the system after a short delay
#
# SAFETY NOTES
#   - This is destructive. Run only on systems you intend to wipe/sanitize.
#   - Keep directory structures under /var/log; remove files only.
#
set -euo pipefail

# Require root
if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo "Please run as root"
  exit 1
fi

# Confirm
read -r -p "WARNING: This will reset settings on this Pi. Continue? (yes/no): " choice
case "${choice}" in
  yes|YES|Yes) echo "Starting reset...";;
  *) echo "Reset cancelled."; exit 0;;
esac

# Make globs safer for rm when nothing matches
shopt -s nullglob

# Clean apt caches
apt-get clean
apt-get autoremove -y || true

# Remove log files but keep directory structure (safer for rsyslog/systemd-journald)
if [[ -d /var/log ]]; then
  find /var/log -type f -print0 | xargs -0r rm -f --
  # Optional: vacuum journald if present
  if command -v journalctl >/dev/null 2>&1; then
    journalctl --rotate || true
    journalctl --vacuum-time=1s || true
  fi
fi

# Clear tmp
rm -rf /tmp/* /var/tmp/* || true

# Reset WSPR-zero (if present)
if [[ -d /opt/wsprzero/wspr-zero ]]; then
  rm -f /opt/wsprzero/wspr-zero/logs/* || true
  rm -f /opt/wsprzero/wspr-zero/wspr-config.json || true
fi

# Remove the WSPR-zero clock calibration file
sudo rm -f /var/lib/wspr-zero/f_pwm_clk

# Clear user histories and caches
for dir in /home/*; do
  [[ -d "$dir" ]] || continue
  rm -f "$dir"/.bash_history || true
  rm -rf "$dir"/.cache/* || true
done
rm -f /root/.bash_history || true
rm -rf /root/.cache/* || true

# Remove DHCP leases (both isc-dhcp and dhcpcd5 on Raspberry Pi OS)
rm -f /var/lib/dhcp/* || true
rm -f /var/lib/dhcpcd5/*.lease || true

# Clear udev rules that can pin old NIC names (harmless if absent)
rm -f /etc/udev/rules.d/70-persistent-net.rules || true
rm -f /lib/udev/rules.d/75-persistent-net-generator.rules || true

# Reset Wi-Fi config to a minimal default with secure perms
install -m 600 -o root -g root /dev/null /etc/wpa_supplicant/wpa_supplicant.conf
cat > /etc/wpa_supplicant/wpa_supplicant.conf <<'EOF'
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
EOF

# Reset machine identity so a new ID is generated on next boot
# (systemd uses /etc/machine-id; D-Bus may also store one)
truncate -s 0 /etc/machine-id
rm -f /var/lib/dbus/machine-id || true

# Reset system SSH host keys
rm -f /etc/ssh/ssh_host_* || true

# Final sync and poweroff
echo "Cleanup complete. Powering off in 10 seconds..."
sleep 10
sync || true
if command -v systemctl >/dev/null 2>&1; then
  systemctl poweroff -i
else
  halt -f
fi

