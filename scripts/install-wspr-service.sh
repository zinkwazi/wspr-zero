#!/usr/bin/env bash
# install-wspr-service.sh
#
# WSPR-zero systemd service installer
# -----------------------------------
# This script installs a systemd unit to start/stop your WSPR controller:
#   /opt/wsprzero/wspr-zero/wspr_control.py
#
# Defaults:
#   - Repo root: /opt/wsprzero/wspr-zero
#   - Service name: wspr.service
#   - Runs as: root
#
# Optional:
#   --with-watch       Install a systemd .path unit to auto-reload the service
#                      whenever /opt/wsprzero/wspr-zero/wspr-config.json changes.
#   --root <dir>       Set a custom repo root (default shown above).
#   --uninstall        Remove the service (and watcher if present).
#   --no-enable        Install units but do not enable/start them.
#
# Quick start:
#   sudo chmod +x scripts/install-wspr-service.sh
#   sudo scripts/install-wspr-service.sh --with-watch
#
# Useful commands:
#   # Service lifecycle
#   sudo systemctl status wspr
#   sudo systemctl start wspr
#   sudo systemctl stop wspr
#   sudo systemctl restart wspr
#   sudo systemctl reload wspr     # re-reads wspr-config.json (stop+start)
#
#   # Logs
#   journalctl -u wspr -f
#   tail -f /opt/wsprzero/wspr-zero/logs/wspr-transmit.log
#   tail -f /opt/wsprzero/wspr-zero/logs/wspr-receive.log
#
#   # Edit config, then reload
#   sudo vi /opt/wsprzero/wspr-zero/wspr-config.json
#   sudo systemctl reload wspr
#
#   # If you installed the watcher:
#   sudo systemctl status wspr.path
#   sudo systemctl disable --now wspr.path
#
# Notes:
#   - python3-psutil is assumed to be installed (per your environment).
#   - wspr_control.py spawns the TX/RX processes and exits; the unit uses
#     Type=oneshot + RemainAfterExit so ExecStop/Reload still work.
#   - Service runs as root (wsprryPi needs elevated access; your Python
#     script also calls sudo internally).
set -euo pipefail

SERVICE_NAME="wspr.service"
RELOAD_SERVICE_NAME="wspr-reload.service"
PATH_UNIT_NAME="wspr.path"

WSPR_ROOT_DEFAULT="/opt/wsprzero/wspr-zero"
WSPR_ROOT="$WSPR_ROOT_DEFAULT"

INSTALL_WATCH=0
UNINSTALL=0
ENABLE_AFTER_INSTALL=1

# -------- arg parsing --------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-watch)
      INSTALL_WATCH=1; shift ;;
    --root)
      WSPR_ROOT="${2:-}"; [[ -z "${WSPR_ROOT}" ]] && { echo "Missing path for --root"; exit 2; }
      shift 2 ;;
    --uninstall)
      UNINSTALL=1; shift ;;
    --no-enable)
      ENABLE_AFTER_INSTALL=0; shift ;;
    -h|--help)
      sed -n '1,120p' "$0"; exit 0 ;;
    *)
      echo "Unknown option: $1"; exit 2 ;;
  esac
done

# -------- helpers --------
need_root() {
  if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    echo "Please run as root (use sudo)." >&2
    exit 1
  fi
}

need_systemd() {
  if ! command -v systemctl >/dev/null 2>&1; then
    echo "systemctl not found; this script requires systemd." >&2
    exit 1
  fi
  if [[ "$(ps -o comm= -p 1)" != "systemd" ]]; then
    echo "PID 1 is not systemd; aborting." >&2
    exit 1
  fi
}

stop_disable_rm_unit() {
  local unit="$1"
  if systemctl list-unit-files | grep -q "^${unit}"; then
    systemctl disable --now "$unit" >/dev/null 2>&1 || true
  fi
  rm -f "/etc/systemd/system/${unit}"
}

# -------- uninstall flow --------
if [[ $UNINSTALL -eq 1 ]]; then
  need_root; need_systemd
  echo "Uninstalling ${SERVICE_NAME} and optional watcher units…"
  stop_disable_rm_unit "$PATH_UNIT_NAME"
  stop_disable_rm_unit "$RELOAD_SERVICE_NAME"
  stop_disable_rm_unit "$SERVICE_NAME"
  systemctl daemon-reload
  echo "Done."
  exit 0
fi

# -------- preflight --------
need_root; need_systemd
if [[ ! -d "$WSPR_ROOT" ]]; then
  echo "Repo root not found: $WSPR_ROOT" >&2
  exit 1
fi
if [[ ! -f "$WSPR_ROOT/wspr_control.py" ]]; then
  echo "Missing controller: $WSPR_ROOT/wspr_control.py" >&2
  exit 1
fi
if [[ ! -x /usr/bin/python3 ]]; then
  echo "/usr/bin/python3 not found or not executable." >&2
  exit 1
fi

# Ensure logs dir exists
mkdir -p "$WSPR_ROOT/logs"

# -------- write wspr.service --------
cat > "/etc/systemd/system/${SERVICE_NAME}" <<EOF
[Unit]
Description=WSPR-zero controller (reads ${WSPR_ROOT}/wspr-config.json)
Wants=network-online.target time-sync.target
After=network-online.target time-sync.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=${WSPR_ROOT}
User=root
ExecStart=/usr/bin/python3 ${WSPR_ROOT}/wspr_control.py start
ExecStop=/usr/bin/python3 ${WSPR_ROOT}/wspr_control.py stop
ExecReload=/bin/bash -lc '/usr/bin/python3 ${WSPR_ROOT}/wspr_control.py stop && sleep 1 && /usr/bin/python3 ${WSPR_ROOT}/wspr_control.py start'
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF
chmod 0644 "/etc/systemd/system/${SERVICE_NAME}"

# -------- optional watcher units --------
if [[ $INSTALL_WATCH -eq 1 ]]; then
  cat > "/etc/systemd/system/${RELOAD_SERVICE_NAME}" <<EOF
[Unit]
Description=Reload WSPR when wspr-config.json changes
Requires=${SERVICE_NAME}
After=${SERVICE_NAME}

[Service]
Type=oneshot
ExecStart=/bin/systemctl reload ${SERVICE_NAME}
EOF
  chmod 0644 "/etc/systemd/system/${RELOAD_SERVICE_NAME}"

  cat > "/etc/systemd/system/${PATH_UNIT_NAME}" <<EOF
[Unit]
Description=Watch wspr-config.json for changes

[Path]
PathModified=${WSPR_ROOT}/wspr-config.json
Unit=${RELOAD_SERVICE_NAME}

[Install]
WantedBy=multi-user.target
EOF
  chmod 0644 "/etc/systemd/system/${PATH_UNIT_NAME}"
fi

# -------- enable/start --------
systemctl daemon-reload

if [[ $ENABLE_AFTER_INSTALL -eq 1 ]]; then
  systemctl enable --now "${SERVICE_NAME}"
  if [[ $INSTALL_WATCH -eq 1 ]]; then
    systemctl enable --now "${PATH_UNIT_NAME}"
  fi
fi

echo "Installed ${SERVICE_NAME} into /etc/systemd/system/."
if [[ $ENABLE_AFTER_INSTALL -eq 1 ]]; then
  echo "Service has been enabled and started."
else
  echo "Units installed but not enabled (per --no-enable)."
fi

if [[ $INSTALL_WATCH -eq 1 ]]; then
  echo "Watcher installed: ${PATH_UNIT_NAME} (auto-reloads on wspr-config.json changes)."
fi

echo "Done."

