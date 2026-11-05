#!/usr/bin/env bash
# 1-Click Always-Free cloud setup for Strategy 3 (Cross-Platform Arbitrage Bot).
# Tested on Ubuntu/Debian (GCP e2-micro Always Free, Oracle Cloud free tier).
set -euo pipefail
SERVICE_NAME="cross_arb_bot"
CRON_NAME="cross_arb_daily_report"
log() { printf "\n[deploy] %s\n" "$*"; }
die() { printf "\n[deploy] ERROR: %s\n" "$*" >&2; exit 1; }
if [[ "${EUID}" -ne 0 ]]; then
  exec sudo -E bash "$0" "$@"
fi
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="${SCRIPT_DIR}"
if [[ ! -f "${REPO_DIR}/run_live_bot.py" ]] || [[ ! -f "${REPO_DIR}/requirements.txt" ]]; then
  die "Run this script from the cloned nba-prediction-market-engine repository (run_live_bot.py missing)."
fi
RUN_USER="${SUDO_USER:-${USER}}"
if [[ -z "${RUN_USER}" || "${RUN_USER}" == "root" ]]; then
  RUN_USER="$(logname 2>/dev/null || echo root)"
fi
RUN_GROUP="$(id -gn "${RUN_USER}" 2>/dev/null || echo "${RUN_USER}")"
log "Installing system packages (python3-pip, python3-venv, git, cron)..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y python3 python3-pip python3-venv git cron ca-certificates
log "Creating Python virtual environment..."
VENV_DIR="${REPO_DIR}/venv"
if [[ ! -d "${VENV_DIR}" ]]; then
  python3 -m venv "${VENV_DIR}"
fi
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"
pip install --upgrade pip
pip install -r "${REPO_DIR}/requirements.txt"
log "Preparing runtime directories..."
mkdir -p "${REPO_DIR}/data/processed" "${REPO_DIR}/logs"
chown -R "${RUN_USER}:${RUN_GROUP}" "${REPO_DIR}/venv" "${REPO_DIR}/data" "${REPO_DIR}/logs"
ENV_FILE="${REPO_DIR}/.env"
if [[ ! -f "${ENV_FILE}" ]]; then
  if [[ -f "${REPO_DIR}/.env.example" ]]; then
    cp "${REPO_DIR}/.env.example" "${ENV_FILE}"
  else
    cat > "${ENV_FILE}" <<'EOF'
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=465
SMTP_USER=
SMTP_PASS=
NOTIFICATION_EMAIL=
EOF
  fi
  chown "${RUN_USER}:${RUN_GROUP}" "${ENV_FILE}"
  chmod 600 "${ENV_FILE}"
  log "Created ${ENV_FILE} — add Gmail SMTP credentials before alerts will send."
else
  log "Keeping existing ${ENV_FILE}"
fi
log "Installing systemd unit /etc/systemd/system/${SERVICE_NAME}.service ..."
cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=NBA Cross-Platform Arbitrage Bot (Strategy 3)
After=network-online.target
Wants=network-online.target
[Service]
Type=simple
User=${RUN_USER}
Group=${RUN_GROUP}
WorkingDirectory=${REPO_DIR}
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONPATH=${REPO_DIR}
EnvironmentFile=-${ENV_FILE}
ExecStart=${VENV_DIR}/bin/python ${REPO_DIR}/run_live_bot.py --interval 5
Restart=always
RestartSec=8
KillSignal=SIGINT
TimeoutStopSec=20
StandardOutput=append:${REPO_DIR}/logs/bot.log
StandardError=append:${REPO_DIR}/logs/bot.err
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}.service"
systemctl restart "${SERVICE_NAME}.service"
log "Installing daily reporter cron job at 20:00 local time..."
systemctl enable --now cron >/dev/null 2>&1 || systemctl enable --now crond >/dev/null 2>&1 || true
CRON_FILE="/etc/cron.d/${CRON_NAME}"
cat > "${CRON_FILE}" <<EOF
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
# Daily 8:00 PM local-time HTML performance email via Gmail SMTP
0 20 * * * ${RUN_USER} cd ${REPO_DIR} && PYTHONPATH=${REPO_DIR} ${VENV_DIR}/bin/python ${REPO_DIR}/src/analytics/reporter.py --send >> ${REPO_DIR}/logs/reporter.log 2>&1
EOF
chmod 644 "${CRON_FILE}"
sleep 2
if systemctl is-active --quiet "${SERVICE_NAME}.service"; then
  log "Service ${SERVICE_NAME}.service is running."
else
  log "Service installed but not yet healthy. Check: journalctl -u ${SERVICE_NAME} -n 50"
  systemctl status "${SERVICE_NAME}.service" --no-pager || true
fi
cat <<EOF
============================================================
 Deployment complete
============================================================
 Repo:            ${REPO_DIR}
 Service:         systemctl status ${SERVICE_NAME}
 Daily report:    20:00 local time via Gmail SMTP
 Env file:        ${ENV_FILE}
 Next: edit ${ENV_FILE} with a Gmail App Password, then:
   sudo systemctl restart ${SERVICE_NAME}
============================================================
EOF
