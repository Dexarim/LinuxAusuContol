#!/usr/bin/env bash
set -Eeuo pipefail

INSTALL_DIR="/opt/asus-control"
BIN_DIR="/usr/local/bin"
SYSTEMD_DIR="/etc/systemd/system"
ENABLE_SERVICE=0
SKIP_DEPS=0
UPDATE_ONLY=0
FORCE_CONFIG=0
ORIGINAL_ARGS=("$@")

usage() {
    cat <<'EOF'
Usage: ./install.sh [options]

Options:
  --install-dir PATH  Install location. Default: /opt/asus-control
  --enable            Enable and start asus-control.service after install
  --update            Update an existing install and preserve config.yaml
  --force-config      Overwrite installed config.yaml with project default
  --skip-deps         Do not install Python dependencies into the venv
  -h, --help          Show this help

Examples:
  ./install.sh
  ./install.sh --enable
  ./install.sh --update
  sudo ./install.sh --install-dir /opt/asus-control --enable
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --install-dir)
            INSTALL_DIR="${2:?Missing value for --install-dir}"
            shift 2
            ;;
        --enable)
            ENABLE_SERVICE=1
            shift
            ;;
        --update)
            UPDATE_ONLY=1
            shift
            ;;
        --force-config)
            FORCE_CONFIG=1
            shift
            ;;
        --skip-deps)
            SKIP_DEPS=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if [[ "${EUID}" -ne 0 ]]; then
    exec sudo bash "$0" "${ORIGINAL_ARGS[@]}"
fi

SOURCE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if [[ "${UPDATE_ONLY}" -eq 1 && ! -d "${INSTALL_DIR}" ]]; then
    echo "ASUS Control is not installed in ${INSTALL_DIR}." >&2
    echo "Run ./install.sh first, or pass the correct --install-dir." >&2
    exit 1
fi

SERVICE_WAS_ACTIVE=0
if systemctl is-active --quiet asus-control.service; then
    SERVICE_WAS_ACTIVE=1
fi

if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python)"
else
    echo "Python 3 was not found. Install python first." >&2
    exit 1
fi

if [[ "${UPDATE_ONLY}" -eq 1 ]]; then
    echo "Updating ASUS Control in ${INSTALL_DIR}"
else
    echo "Installing ASUS Control to ${INSTALL_DIR}"
fi
install -d \
    "${INSTALL_DIR}" \
    "${INSTALL_DIR}/asus_control" \
    "${INSTALL_DIR}/config" \
    "${INSTALL_DIR}/systemd" \
    "${BIN_DIR}" \
    "${SYSTEMD_DIR}"

install -m 0644 \
    "${SOURCE_DIR}/asus_control/"*.py \
    "${INSTALL_DIR}/asus_control/"

install -m 0644 \
    "${SOURCE_DIR}/cli.py" \
    "${SOURCE_DIR}/daemon.py" \
    "${SOURCE_DIR}/requirements.txt" \
    "${SOURCE_DIR}/pyproject.toml" \
    "${SOURCE_DIR}/README.md" \
    "${SOURCE_DIR}/install.sh" \
    "${INSTALL_DIR}/"

if [[ -f "${INSTALL_DIR}/config/config.yaml" && "${FORCE_CONFIG}" -eq 0 ]]; then
    install -m 0644 "${SOURCE_DIR}/config/config.yaml" "${INSTALL_DIR}/config/config.yaml.example"
    echo "Preserved existing config: ${INSTALL_DIR}/config/config.yaml"
    echo "New default config saved as: ${INSTALL_DIR}/config/config.yaml.example"
else
    install -m 0644 "${SOURCE_DIR}/config/config.yaml" "${INSTALL_DIR}/config/config.yaml"
fi

install -m 0644 \
    "${SOURCE_DIR}/systemd/asus-control.service" \
    "${SOURCE_DIR}/systemd/asus-control.timer" \
    "${INSTALL_DIR}/systemd/"

cat > "${INSTALL_DIR}/systemd/asus-control.service" <<EOF
[Unit]
Description=Linux ASUS Control automation daemon
After=multi-user.target

[Service]
Type=simple
WorkingDirectory=${INSTALL_DIR}
ExecStart=${INSTALL_DIR}/.venv/bin/python -m asus_control.daemon --config ${INSTALL_DIR}/config/config.yaml
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

"${PYTHON_BIN}" -m venv "${INSTALL_DIR}/.venv"

if [[ "${SKIP_DEPS}" -eq 0 ]]; then
    "${INSTALL_DIR}/.venv/bin/python" -m pip install --upgrade pip
    "${INSTALL_DIR}/.venv/bin/python" -m pip install -r "${INSTALL_DIR}/requirements.txt"
fi

cat > "${BIN_DIR}/fan" <<EOF
#!/usr/bin/env bash
cd "${INSTALL_DIR}"
exec "${INSTALL_DIR}/.venv/bin/python" -m asus_control.cli "\$@"
EOF
chmod 0755 "${BIN_DIR}/fan"

cat > "${BIN_DIR}/asus-control-daemon" <<EOF
#!/usr/bin/env bash
cd "${INSTALL_DIR}"
exec "${INSTALL_DIR}/.venv/bin/python" -m asus_control.daemon --config "${INSTALL_DIR}/config/config.yaml" "\$@"
EOF
chmod 0755 "${BIN_DIR}/asus-control-daemon"

install -m 0644 "${INSTALL_DIR}/systemd/asus-control.service" "${SYSTEMD_DIR}/asus-control.service"
install -m 0644 "${INSTALL_DIR}/systemd/asus-control.timer" "${SYSTEMD_DIR}/asus-control.timer"

systemctl daemon-reload

if [[ "${ENABLE_SERVICE}" -eq 1 ]]; then
    systemctl enable --now asus-control.service
elif [[ "${SERVICE_WAS_ACTIVE}" -eq 1 ]]; then
    systemctl restart asus-control.service
fi

cat <<EOF

ASUS Control $([[ "${UPDATE_ONLY}" -eq 1 ]] && echo "updated" || echo "installed").

Commands:
  fan
  fan status
  fan version
  fan json
  fan journal
  fan dbus --bus session
  sudo fan basic
  sudo fan performance
  sudo asus-control-daemon --once

Service:
  sudo systemctl enable --now asus-control.service
  sudo systemctl restart asus-control.service
  journalctl -u asus-control.service -f

Config:
  ${INSTALL_DIR}/config/config.yaml
EOF
