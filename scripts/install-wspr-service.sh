#!/usr/bin/env bash
# install-wspr-service.sh
#
# WSPR-zero systemd service installer
# -----------------------------------
# Installs a systemd unit to control WSPR using:
#   /opt/wsprzero/wspr-zero/scripts/wspr_control.py
#
# Defaults:
#   - Repo root: /opt/wsprzero/wspr-zero
#   - Service:   wspr-service.service  (enabled & started unless --no-enable)
#   - Watcher:   wspr-service.path     (installed by default; see INSTALL_WATCH)
#
# Optional flags (kept the same):
#   --with-watch       Auto-reload on wspr-config.json changes (no-op: default on)
#   --root <dir>       Custom repo root (default above)
#   --uninstall        Remove service (and watcher if present)
#   --no-enable        Install but don’t enable/start
#
# Quick start:
#   sudo chmod +x scripts/install-wspr-service.sh
#   sudo scripts/install-wspr-service.sh
#
# Useful commands:
#   # Service lifecycle
#   sudo systemctl status  wspr-service
#   sudo systemctl start   wspr-service
#   sudo systemctl stop    wspr-service
#   sudo systemctl restart wspr-service
#   sudo systemctl reload  wspr-service   # stop+start to re-read JSON
#
#   # Logs
#   journalctl -u wspr-service -f
#   tail -f /opt/wsprzero/wspr-zero/logs/wspr-transmit.log
#   tail -f /opt/wsprzero/wspr-zero/logs/wspr-receive.log
#
#   # Edit config, then reload
#   sudo vi /opt/wsprzero/wspr-zero/wspr-config.json
#   sudo systemctl reload wspr-service
#
# Notes:
#   - python3-psutil is assumed present.
#   - Unit uses Type=oneshot + RemainAfterExit so ExecStop/Reload work.
#   - Runs as root (wsprryPi/kill operations often need it).
set -euo pipefail

SERVICE_NAME="wspr-service.service"
RELOAD_SERVICE_NAME="wspr-service-reload.service"
PATH_UNIT_NAME="wspr-service.path"

WSPR_ROOT_DEFAULT="/opt/wsprzero/wspr-zero"
WSPR_ROOT="$WSPR_ROOT_DEFAULT"
CONTROLLER=""  # set after WSPR_ROOT

INSTALL_WATCH=1
UNINSTALL=0
ENABLE_AFTER_INSTALL=1

# -------- args --------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-watch) INSTALL_WATCH=1; shift ;;  # default already on
    --root) WSPR_ROOT="${2:-}"; [[ -z "${WSPR_ROOT}" ]] && { echo "Missing path for --root"; exit 2; }; shift 2 ;;
    --uninstall) UNINSTALL=1; shift ;;
    --no-enable) ENABLE_AFTER_INSTALL=0; shift ;;
    -h|--help) sed -n '1,160p' "$0"; exit 0 ;;
    *) echo "Unknown option: $1"; exit 2 ;;
  esac
done

CONTROLLER="${WSPR_ROOT}/scripts/wspr_control.py"

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

# -------- uninstall --------
if [[ $UNINSTALL -eq 1 ]]; then
  need_root; need_systemd
  echo "Uninstalling ${SERVICE_NAME} and optional watcher…"
  stop_disable_rm_unit "$PATH_UNIT_NAME"
  stop_disable_rm_unit "$RELOAD_SERVICE_NAME"
  stop_disable_rm_unit "$SERVICE_NAME"
  systemctl daemon-reload
  echo "Done."
  exit 0
fi

# -------- preflight --------
need_root; need_systemd
[[ -d "$WSPR_ROOT" ]] || { echo "Repo root not found: $WSPR_ROOT" >&2; exit 1; }
[[ -f "$CONTROLLER" ]] || { echo "Controller not found: $CONTROLLER" >&2; exit 1; }
[[ -x /usr/bin/python3 ]] || { echo "/usr/bin/python3 not found." >&2; exit 1; }

# Ensure logs dir
mkdir -p "$WSPR_ROOT/logs"

# -------- write wspr-service.service --------
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
Environment=PYTHONUNBUFFERED=1
ExecStart=/usr/bin/python3 ${CONTROLLER} start
ExecStop=/usr/bin/python3 ${CONTROLLER} stop
ExecReload=/bin/bash -lc '/usr/bin/python3 ${CONTROLLER} stop && sleep 1 && /usr/bin/python3 ${CONTROLLER} start'
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF
chmod 0644 "/etc/systemd/system/${SERVICE_NAME}"

# -------- optional watcher (.path + reload service) --------
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
# Use both to catch in-place writes and atomic replaces (vim, etc.)
PathChanged=${WSPR_ROOT}/wspr-config.json
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

echo "Installed ${SERVICE_NAME} (controller: ${CONTROLLER})."
[[ $ENABLE_AFTER_INSTALL -eq 1 ]] && echo "Service enabled and started."
[[ $INSTALL_WATCH -eq 1 ]] && echo "Watcher installed: ${PATH_UNIT_NAME}."
echo "Done."

