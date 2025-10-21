#!/usr/bin/env bash
# install-wspr-aux.sh
#
# Installs WSPR-zero aux systemd units:
#   1) wspr-server-checkin.service  (oneshot @ boot + on-demand)
#   2) wspr-utility-button.service  (continuous; auto-restart)
#
# Defaults:
#   - Repo root:  /opt/wsprzero/wspr-zero
#   - Both units installed & enabled unless flags say otherwise
#
# Flags:
#   --root <dir>        Custom repo root (default above)
#   --no-enable         Install units but don't enable/start
#   --uninstall         Remove aux units (leaves wspr-service alone)
#   --checkin-only      Install only the check-in unit
#   --button-only       Install only the utility-button unit
#
# Quick start:
#   sudo chmod +x scripts/install-wspr-aux.sh
#   sudo scripts/install-wspr-aux.sh
#
# Useful:
#   # Run a check-in on demand
#   sudo systemctl start wspr-server-checkin.service
#
#   # Button service status
#   systemctl status wspr-utility-button.service
#
set -euo pipefail

# ---------- config ----------
WSPR_ROOT_DEFAULT="/opt/wsprzero/wspr-zero"
WSPR_ROOT="$WSPR_ROOT_DEFAULT"

CHECKIN_UNIT="wspr-server-checkin.service"
BUTTON_UNIT="wspr-utility-button.service"
MAIN_SERVICE="wspr-service.service"

INSTALL_CHECKIN=1
INSTALL_BUTTON=1
ENABLE_AFTER_INSTALL=1
UNINSTALL=0

# ---------- args ----------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --root)        WSPR_ROOT="${2:-}"; [[ -z "$WSPR_ROOT" ]] && { echo "Missing --root path"; exit 2; }; shift 2 ;;
    --no-enable)   ENABLE_AFTER_INSTALL=0; shift ;;
    --uninstall)   UNINSTALL=1; shift ;;
    --checkin-only) INSTALL_CHECKIN=1; INSTALL_BUTTON=0; shift ;;
    --button-only)  INSTALL_CHECKIN=0; INSTALL_BUTTON=1; shift ;;
    -h|--help)     sed -n '1,200p' "$0"; exit 0 ;;
    *)             echo "Unknown option: $1"; exit 2 ;;
  esac
done

CHECKIN_SCRIPT="${WSPR_ROOT}/scripts/server_checkin.py"
BUTTON_SCRIPT="${WSPR_ROOT}/scripts/utility-button.py"
CONFIG_JSON="${WSPR_ROOT}/wspr-config.json"

# ---------- helpers ----------
need_root() {
  if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    echo "Please run as root (sudo)." >&2
    exit 1
  fi
}
need_systemd() {
  command -v systemctl >/dev/null 2>&1 || { echo "systemctl not found"; exit 1; }
  [[ "$(ps -o comm= -p 1)" == "systemd" ]] || { echo "PID1 is not systemd"; exit 1; }
}
stop_disable_rm() {
  local unit="$1"
  if systemctl list-unit-files | grep -q "^${unit}"; then
    systemctl disable --now "$unit" >/dev/null 2>&1 || true
  fi
  rm -f "/etc/systemd/system/${unit}"
}
uninstall_all() {
  echo "Uninstalling aux units…"
  stop_disable_rm "$CHECKIN_UNIT"
  stop_disable_rm "$BUTTON_UNIT"
  systemctl daemon-reload
  echo "Done."
}

write_checkin_unit() {
  cat > "/etc/systemd/system/${CHECKIN_UNIT}" <<EOF
[Unit]
Description=WSPR-zero one-shot server check-in (LED blink + remote config pull)
Wants=network-online.target
After=network-online.target
Before=${MAIN_SERVICE}
ConditionPathExists=${CHECKIN_SCRIPT}

[Service]
Type=oneshot
WorkingDirectory=${WSPR_ROOT}
User=root
UMask=0002
Environment=PYTHONUNBUFFERED=1

# If main service running (manual start), stop it first; ignore error if inactive
ExecStartPre=-/bin/systemctl stop ${MAIN_SERVICE}

# Do the check-in (LED, server pull, write config)
ExecStart=/usr/bin/python3 ${CHECKIN_SCRIPT}

# Start/restart main service after check-in
ExecStartPost=-/bin/systemctl start ${MAIN_SERVICE}

[Install]
WantedBy=multi-user.target
EOF
  chmod 0644 "/etc/systemd/system/${CHECKIN_UNIT}"
}

write_button_unit() {
  cat > "/etc/systemd/system/${BUTTON_UNIT}" <<EOF
[Unit]
Description=WSPR-zero utility button (GPIO 19; 5x = setup, 10s hold = shutdown)
After=multi-user.target
ConditionPathExists=${BUTTON_SCRIPT}

[Service]
Type=simple
WorkingDirectory=${WSPR_ROOT}
User=root
UMask=0002
Environment=PYTHONUNBUFFERED=1
ExecStart=/usr/bin/python3 ${BUTTON_SCRIPT}
Restart=always
RestartSec=2
KillMode=process

[Install]
WantedBy=multi-user.target
EOF
  chmod 0644 "/etc/systemd/system/${BUTTON_UNIT}"
}

# ---------- main ----------
need_root
need_systemd

if [[ $UNINSTALL -eq 1 ]]; then
  uninstall_all
  exit 0
fi

[[ -d "$WSPR_ROOT" ]] || { echo "Repo root not found: $WSPR_ROOT"; exit 1; }
[[ $INSTALL_CHECKIN -eq 0 || -f "$CHECKIN_SCRIPT" ]] || { echo "Missing $CHECKIN_SCRIPT"; exit 1; }
[[ $INSTALL_BUTTON  -eq 0 || -f "$BUTTON_SCRIPT"  ]] || { echo "Missing $BUTTON_SCRIPT"; exit 1; }

# make sure logs dir exists & is group-writable (idempotent; matches main installer)
mkdir -p "${WSPR_ROOT}/logs"
getent group wsprzero >/dev/null || groupadd --system wsprzero
chgrp -R wsprzero "${WSPR_ROOT}/logs"
find "${WSPR_ROOT}/logs" -type d -exec chmod 2775 {} +
find "${WSPR_ROOT}/logs" -type f -exec chmod 0664 {} + || true

# write units
[[ $INSTALL_CHECKIN -eq 1 ]] && write_checkin_unit
[[ $INSTALL_BUTTON  -eq 1 ]] && write_button_unit

systemctl daemon-reload

if [[ $ENABLE_AFTER_INSTALL -eq 1 ]]; then
  [[ $INSTALL_CHECKIN -eq 1 ]] && systemctl enable --now "${CHECKIN_UNIT}"
  [[ $INSTALL_BUTTON  -eq 1 ]] && systemctl enable --now "${BUTTON_UNIT}"
fi

echo "Installed aux units:"
[[ $INSTALL_CHECKIN -eq 1 ]] && echo "  - ${CHECKIN_UNIT}"
[[ $INSTALL_BUTTON  -eq 1 ]] && echo "  - ${BUTTON_UNIT}"
echo "Done."

