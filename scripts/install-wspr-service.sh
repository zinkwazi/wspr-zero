#!/usr/bin/env bash
# install-wspr-service.sh
#
# WSPR-zero systemd service installer
# -----------------------------------
# Installs systemd units to control WSPR using:
#   /opt/wsprzero/wspr-zero/scripts/wspr_control.py
#
# Defaults:
#   - Repo root:  /opt/wsprzero/wspr-zero
#   - Service:    wspr-service.service  (enabled & started unless --no-enable)
#   - Mode:       supervised (auto-restart if child dies; prefers robustness)
#   - Watcher:    wspr-service.path     (installed by default; triggers reload)
#
# Optional flags:
#   --root <dir>       Custom repo root (default above)
#   --no-enable        Install but don’t enable/start
#   --uninstall        Remove service + watcher
#   --no-watch         Don’t install the watcher
#   --supervised       Force supervised mode (default)
#   --oneshot          Install legacy oneshot unit (no auto-restart)
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
#   sudo systemctl reload  wspr-service   # supervisor catches SIGHUP, reloads JSON
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
#   - Supervised mode uses: Type=simple + Restart=always and runs: wspr_control.py run
#   - Oneshot mode remains available (no auto-restart).
set -euo pipefail

SERVICE_NAME="wspr-service.service"
RELOAD_SERVICE_NAME="wspr-service-reload.service"
PATH_UNIT_NAME="wspr-service.path"

# legacy names to purge if they still exist
LEGACY_UNITS=("wspr.service" "wspr.path" "wspr-reload.service")

WSPR_ROOT_DEFAULT="/opt/wsprzero/wspr-zero"
WSPR_ROOT="$WSPR_ROOT_DEFAULT"
CONTROLLER=""  # set after WSPR_ROOT

INSTALL_WATCH=1
UNINSTALL=0
ENABLE_AFTER_INSTALL=1
SERVICE_MODE="supervised"   # default; set to "oneshot" with --oneshot

# -------- args --------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --root)        WSPR_ROOT="${2:-}"; [[ -z "${WSPR_ROOT}" ]] && { echo "Missing path for --root"; exit 2; }; shift 2 ;;
    --no-enable)   ENABLE_AFTER_INSTALL=0; shift ;;
    --uninstall)   UNINSTALL=1; shift ;;
    --no-watch)    INSTALL_WATCH=0; shift ;;
    --supervised)  SERVICE_MODE="supervised"; shift ;;
    --oneshot)     SERVICE_MODE="oneshot"; shift ;;
    -h|--help)     sed -n '1,200p' "$0"; exit 0 ;;
    *)             echo "Unknown option: $1"; exit 2 ;;
  esac
done

CONTROLLER="${WSPR_ROOT}/scripts/wspr_control.py"
CONFIG_JSON="${WSPR_ROOT}/wspr-config.json"

# -------- helpers --------
need_root() {
  if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    echo "Please run as root (use sudo)." >&2
    exit 1
  fi
}
need_systemd() {
  command -v systemctl >/dev/null 2>&1 || { echo "systemctl not found."; exit 1; }
  [[ "$(ps -o comm= -p 1)" == "systemd" ]] || { echo "PID 1 is not systemd."; exit 1; }
}
stop_disable_rm_unit() {
  local unit="$1"
  if systemctl list-unit-files | grep -q "^${unit}"; then
    systemctl disable --now "${unit}" >/dev/null 2>&1 || true
  fi
  rm -f "/etc/systemd/system/${unit}"
}
uninstall_all() {
  echo "Uninstalling ${SERVICE_NAME} and watcher…"
  stop_disable_rm_unit "${PATH_UNIT_NAME}"
  stop_disable_rm_unit "${RELOAD_SERVICE_NAME}"
  stop_disable_rm_unit "${SERVICE_NAME}"
  # also clean any legacy-named units
  for u in "${LEGACY_UNITS[@]}"; do stop_disable_rm_unit "$u"; done
  systemctl daemon-reload
  echo "Done."
}

write_service_unit_supervised() {
  cat > "/etc/systemd/system/${SERVICE_NAME}" <<EOF
[Unit]
Description=WSPR-zero controller (reads ${CONFIG_JSON})
Wants=network-online.target time-sync.target
After=network-online.target time-sync.target
ConditionPathExists=${CONTROLLER}

[Service]
Type=simple
WorkingDirectory=${WSPR_ROOT}
User=root
UMask=0002
Environment=PYTHONUNBUFFERED=1
Restart=always
RestartSec=5
KillMode=control-group
ExecStart=/usr/bin/python3 ${CONTROLLER} run
ExecReload=/bin/kill -HUP \$MAINPID
ExecStop=/bin/kill -TERM \$MAINPID
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF
  chmod 0644 "/etc/systemd/system/${SERVICE_NAME}"
}

write_service_unit_oneshot() {
  cat > "/etc/systemd/system/${SERVICE_NAME}" <<EOF
[Unit]
Description=WSPR-zero controller (reads ${CONFIG_JSON})
Wants=network-online.target time-sync.target
After=network-online.target time-sync.target
ConditionPathExists=${CONTROLLER}

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
}

write_watcher_units() {
  cat > "/etc/systemd/system/${RELOAD_SERVICE_NAME}" <<EOF
[Unit]
Description=Reload wspr-service when wspr-config.json changes
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
PathChanged=${CONFIG_JSON}
PathModified=${CONFIG_JSON}
Unit=${RELOAD_SERVICE_NAME}

[Install]
WantedBy=multi-user.target
EOF
  chmod 0644 "/etc/systemd/system/${PATH_UNIT_NAME}"
}

# -------- main --------
need_root
need_systemd

# -------- SSH host keys (recreate if missing) --------
ensure_ssh_host_keys() {
  # If any private host key exists, assume SSH is already provisioned
  if ls /etc/ssh/ssh_host_*_key >/dev/null 2>&1; then
    echo "SSH host keys already present."
  else
    echo "Recreating SSH host keys..."
    if ! command -v ssh-keygen >/dev/null 2>&1; then
      echo "Warning: ssh-keygen not found. Install openssh-server before running this installer." >&2
      return 0
    fi
    ssh-keygen -A
  fi

  # Normalize permissions (safe if keys already existed)
  chown -R root:root /etc/ssh || true
  chmod 600 /etc/ssh/ssh_host_*_key 2>/dev/null || true
  chmod 644 /etc/ssh/ssh_host_*_key.pub 2>/dev/null || true

  # Make sure SSH will start on boot and is running now
  if command -v systemctl >/dev/null 2>&1; then
    systemctl enable ssh >/dev/null 2>&1 || true
    systemctl restart ssh >/dev/null 2>&1 || true
    systemctl --no-pager --quiet is-active ssh || {
      echo "Warning: ssh.service is not active; check 'journalctl -u ssh'." >&2
    }
  else
    echo "Note: systemd not available; skipping ssh.service enable/restart." >&2
  fi

  # Optional: headless-enable flag on boot partition(s)
  if [[ -d /boot/firmware ]]; then : > /boot/firmware/ssh; fi
  if [[ -d /boot ]]; then : > /boot/ssh; fi
}

# call it early so remote access is available even if the rest fails later
ensure_ssh_host_keys



# -------- build & install WsprryPi-zero --------
WSPRRYP_DIR="/opt/wsprzero/WsprryPi-zero"

build_wsprry() {
  if [[ ! -d "$WSPRRYP_DIR" ]]; then
    echo "WsprryPi-zero source not found at $WSPRRYP_DIR — skipping build."
    return 0
  fi

  echo "Building WsprryPi-zero in $WSPRRYP_DIR ..."
  pushd "$WSPRRYP_DIR" >/dev/null

  # Clean old artifacts (ignore errors if nothing to clean)
  make clean || true

  # Build using available cores
  make -j"$(nproc)"

  # Install the binary somewhere on PATH
  install -m 0755 wspr /usr/local/bin/wspr

  popd >/dev/null
  echo "WsprryPi-zero build complete. Installed /usr/local/bin/wspr"
}

# call the builder before installing/enabling units
build_wsprry

if [[ $UNINSTALL -eq 1 ]]; then
  uninstall_all
  exit 0
fi

[[ -d "$WSPR_ROOT" ]] || { echo "Repo root not found: $WSPR_ROOT"; exit 1; }
[[ -f "$CONTROLLER" ]] || { echo "Controller not found: $CONTROLLER"; exit 1; }
command -v /usr/bin/python3 >/dev/null 2>&1 || { echo "/usr/bin/python3 not found."; exit 1; }

# ensure logs dir exists for first run
mkdir -p "${WSPR_ROOT}/logs"
# ensure logs stay group-inheriting & writable
getent group wsprzero >/dev/null || groupadd --system wsprzero
chgrp -R wsprzero "${WSPR_ROOT}/logs"
# SGID on dirs so new files inherit the wsprzero group
find "${WSPR_ROOT}/logs" -type d -exec chmod 2775 {} +
# regular files rw-rw-r--
find "${WSPR_ROOT}/logs" -type f -exec chmod 0664 {} + || true

# (optional) let the login user read journals & logs without sudo
if id -u wsprzero >/dev/null 2>&1; then
  usermod -aG wsprzero,systemd-journal wsprzero || true
fi

# purge any legacy-named units to avoid confusion
for u in "${LEGACY_UNITS[@]}"; do stop_disable_rm_unit "$u"; done

# write the chosen service unit
if [[ "$SERVICE_MODE" == "supervised" ]]; then
  write_service_unit_supervised
else
  write_service_unit_oneshot
fi

# watcher (default ON; opt-out with --no-watch)
if [[ $INSTALL_WATCH -eq 1 ]]; then
  write_watcher_units
fi

systemctl daemon-reload

if [[ $ENABLE_AFTER_INSTALL -eq 1 ]]; then
  systemctl enable --now "${SERVICE_NAME}"
  if [[ $INSTALL_WATCH -eq 1 ]]; then
    systemctl enable --now "${PATH_UNIT_NAME}"
  fi
fi

echo "Installed ${SERVICE_NAME} in ${SERVICE_MODE} mode (controller: ${CONTROLLER})."
[[ $ENABLE_AFTER_INSTALL -eq 1 ]] && echo "Service enabled and started."
[[ $INSTALL_WATCH -eq 1 ]] && echo "Watcher installed: ${PATH_UNIT_NAME}."
echo "Done."

