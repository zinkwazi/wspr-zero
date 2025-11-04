#!/bin/bash
# reset-img.sh — sanitize and prep a WSPR-zero Raspberry Pi image for redistribution
#
# Keeps Raspberry Pi Imager compatibility:
#  - Leave first-boot machinery intact (raspberrypi-sys-mods, raspi-config hooks)
#  - Ensure SSH can be enabled via boot flag (and/or Imager advanced options)
#  - Let Imager drop wpa_supplicant.conf/userconf.txt/hostname on /boot(/firmware)
#  - Remove host keys so they regenerate; clear machine-id; no saved Wi-Fi
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

# --- Stop WSPR-zero services (from installers) before proceeding
if command -v systemctl >/dev/null 2>&1; then
  # Units from install-wspr-service.sh and install-wspr-aux.sh
  SERVICES=(
    wspr-service.service
    wspr-service-reload.service
    wspr-service.path
    wspr-server-checkin.service
    wspr-utility-button.service
    wspr-boot-config.service
    # legacy names to be safe
    wspr.service
    wspr.path
    wspr-reload.service
  )

  # Stop, disable, and (optionally) mask to prevent any restarts during reset
  for svc in "${SERVICES[@]}"; do
    if systemctl list-unit-files | grep -qE "^${svc}\b"; then
      systemctl stop "$svc" >/dev/null 2>&1 || true
      systemctl disable "$svc" >/dev/null 2>&1 || true
      systemctl mask "$svc" >/dev/null 2>&1 || true
    fi
  done

  # Clear any failed state noise
  systemctl reset-failed >/dev/null 2>&1 || true
  systemctl daemon-reload || true
else
  # SysV-style fallback for very old images (best-effort)
  for svc in wspr-service wspr-service-reload wspr-server-checkin wspr-utility-button wspr-boot-config wspr; do
    service "$svc" stop >/dev/null 2>&1 || true
    update-rc.d -f "$svc" remove >/dev/null 2>&1 || true
  done
fi

# Belt-and-suspenders: kill any stragglers started outside systemd
pkill -x wspr                     >/dev/null 2>&1 || true
pkill -f 'rtlsdr-wsprd'          >/dev/null 2>&1 || true
pkill -f '/scripts/wspr_control\.py'   >/dev/null 2>&1 || true
pkill -f '/scripts/server_checkin\.py' >/dev/null 2>&1 || true
pkill -f '/scripts/utility-button\.py' >/dev/null 2>&1 || true

# --- (A) Ensure required packages / services for first-boot & SSH are present ---
if command -v apt-get >/dev/null 2>&1; then
  # Openssh-server provides sshd + ssh-keygen -A (for first-boot regen)
  # raspberrypi-sys-mods/raspi-config carry the first-boot importers used by Imager
  apt-get update -y || true
  DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    openssh-server raspberrypi-sys-mods raspi-config || true
fi

# Always keep SSH service enabled (Imager can also enable via boot flag)
systemctl enable ssh >/dev/null 2>&1 || true

# --- (B) Clean apt caches
if command -v apt-get >/dev/null 2>&1; then
  apt-get clean || true
  apt-get autoremove -y || true
fi

# --- (C) Remove log files but keep directory structure
if [[ -d /var/log ]]; then
  find /var/log -type f -print0 | xargs -0r rm -f --
  if command -v journalctl >/dev/null 2>&1; then
    journalctl --rotate || true
    journalctl --vacuum-time=1s || true
  fi
fi

# --- (D) Clear tmp
rm -rf /tmp/* /var/tmp/* || true

# --- (E) Reset WSPR-zero state (if present)
if [[ -d /opt/wsprzero/wspr-zero ]]; then
  rm -f /opt/wsprzero/wspr-zero/logs/* || true
  rm -f /opt/wsprzero/wspr-zero/wspr-config.json || true
fi

# Remove the WSPR-zero clock calibration file
rm -f /var/lib/wspr-zero/f_pwm_clk || true

# --- (F) Remove the 'pi' account so Raspberry Pi Imager can recreate it
# IMPORTANT: do not run this while logged in as 'pi'
if id -u pi >/dev/null 2>&1; then
  # Refuse to proceed if the interactive or sudo-invoking user is 'pi'
  if [[ "${SUDO_USER:-}" == "pi" ]] || [[ "$(logname 2>/dev/null || echo '')" == "pi" ]]; then
    echo "Refusing to remove 'pi' while the current session user is 'pi'."
    echo "Log in as root or another user and re-run."
    exit 1
  fi

  echo "Removing 'pi' user so first-boot can recreate it…"

  # Stop anything still running as 'pi'
  pkill -u pi  >/dev/null 2>&1 || true

  # Clear 'pi' crontab (both crontab and spool, if present)
  crontab -r -u pi 2>/dev/null || true
  rm -f /var/spool/cron/crontabs/pi 2>/dev/null || true

  # Remove the common sudoers exception for 'pi'
  rm -f /etc/sudoers.d/010_pi-nopasswd 2>/dev/null || true

  # Reassign ownership of WSPR-zero dirs if they were owned by 'pi'
  chown -R root:root /opt/wsprzero 2>/dev/null || true
  chown -R root:root /var/lib/wspr-zero 2>/dev/null || true

  # Mailbox and AccountsService residue
  rm -f /var/mail/pi 2>/dev/null || true
  rm -f /var/lib/AccountsService/users/pi 2>/dev/null || true

  # Remove subuid/subgid mappings if present
  sed -i '/^pi:/d' /etc/subuid 2>/dev/null || true
  sed -i '/^pi:/d' /etc/subgid 2>/dev/null || true

  # Delete the user (and home), then the group if empty
  userdel -r pi 2>/dev/null || deluser --remove-home pi 2>/dev/null || true
  if getent group pi >/dev/null 2>&1; then
    groupdel pi 2>/dev/null || true
  fi
fi

# --- (G) Clear user histories and caches
for dir in /home/*; do
  [[ -d "$dir" ]] || continue
  rm -f "$dir"/.bash_history || true
  rm -rf "$dir"/.cache/* || true
done
rm -f /root/.bash_history || true
rm -rf /root/.cache/* || true

# Extra user history/artifacts
for dir in /home/*; do
  [[ -d "$dir" ]] || continue
  rm -f "$dir"/.zsh_history "$dir"/.viminfo "$dir"/.lesshst "$dir"/.python_history 2>/dev/null || true
done
rm -f /root/.zsh_history /root/.viminfo /root/.lesshst /root/.python_history 2>/dev/null || true

# Unique entropy on first boot
rm -f /var/lib/systemd/random-seed || true

# --- (H) Remove DHCP leases (isc-dhcp & dhcpcd)
rm -f /var/lib/dhcp/* || true
rm -f /var/lib/dhcpcd5/*.lease || true

# --- (I) Clear udev rules that can pin old NIC names
rm -f /etc/udev/rules.d/70-persistent-net.rules || true
rm -f /lib/udev/rules.d/75-persistent-net-generator.rules || true

# --- (J) Wi-Fi: Let Raspberry Pi Imager supply Wi-Fi at first boot
rm -f /etc/wpa_supplicant/wpa_supplicant.conf
rm -f /etc/NetworkManager/system-connections/*.nmconnection 2>/dev/null || true

# NOTE: Do NOT add any network={...} here; Raspberry Pi Imager will place a full
# wpa_supplicant.conf on the boot partition that first-boot will import/use.

# --- (K) Reset machine identity so first boot generates fresh IDs
truncate -s 0 /etc/machine-id
rm -f /var/lib/dbus/machine-id || true

# --- (L) Reset system SSH host keys (regenerated on first boot)
#rm -f /etc/ssh/ssh_host_* || true

# --- (M) Headless-enable flag: allow SSH even if user forgets to tick it in Imager
if [[ -d /boot/firmware ]]; then
  : > /boot/firmware/ssh
  chmod 0644 /boot/firmware/ssh || true   # VFAT perms are cosmetic; harmless
fi
if [[ -d /boot ]]; then
  : > /boot/ssh
  chmod 0644 /boot/ssh || true
fi
if [[ ! -d /boot/firmware && ! -d /boot ]]; then
  echo "WARNING: No /boot or /boot/firmware found; cannot create SSH flag." >&2
fi

# --- (N) Make space for Imager’s first-boot metadata (optional hygiene)
# If any exist, clear stale files so Imager’s versions are authoritative.
rm -f /boot/firmware/userconf.txt /boot/userconf.txt 2>/dev/null || true
rm -f /boot/firmware/hostname /boot/hostname 2>/dev/null || true
rm -f /boot/firmware/wpa_supplicant.conf /boot/wpa_supplicant.conf 2>/dev/null || true

# --- (O) Reset locale and re-arm first-boot timezone auto-detect
# Clear static locale so first boot isn't pinned to your build locale
rm -f /etc/default/locale 2>/dev/null || true
# Scrub any LC_* and LANG in /etc/environment so shells don't inherit stale values
if [[ -f /etc/environment ]]; then
  sed -i '/^LC_/d' /etc/environment 2>/dev/null || true
  sed -i '/^LANG=/d' /etc/environment 2>/dev/null || true
fi

# Make sure the auto-timezone runs on the next boot (and keeps trying until online)
rm -f /var/lib/wspr/auto-tz.done 2>/dev/null || true
systemctl enable wspr-auto-tz.service >/dev/null 2>&1 || true

# Optional: do NOT delete /etc/localtime; the service will overwrite if needed
# Optional: if you previously silenced cloud-init's locale banner, undo that
rm -f /var/lib/cloud/instance/locale-check.skip 2>/dev/null || true

# Final sync and poweroff
echo "Cleanup complete. Ready for Raspberry Pi Imager 'Use custom image'. Powering off in 3 seconds..."
sleep 3
sync || true
if command -v systemctl >/dev/null 2>&1; then
  systemctl poweroff -i
else
  halt -f
fi

