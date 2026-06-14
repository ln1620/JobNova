#!/usr/bin/env bash
# EC2 setup for JobNova apply worker (Amazon Linux).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USER_HOME="${HOME:-/home/ec2-user}"

echo "[ec2] Installing Chrome, Xvfb, x11vnc..."
sudo yum install -y wget xorg-x11-server-Xvfb x11vnc python3 python3-pip

if ! command -v google-chrome-stable &>/dev/null; then
  wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_x86_64.rpm
  sudo yum install -y ./google-chrome-stable_current_x86_64.rpm || true
  rm -f google-chrome-stable_current_x86_64.rpm
fi

echo "[ec2] Copying extension..."
sudo mkdir -p /opt/jobnova
sudo cp -r "$ROOT/extensions/auto-apply" "$USER_HOME/jobnova-extension"
sudo chown -R "$(whoami):$(whoami)" "$USER_HOME/jobnova-extension"

mkdir -p "$USER_HOME/chrome-profile"
mkdir -p /tmp/jobnova-resumes

echo "[ec2] Installing apply worker..."
cd "$ROOT/services/apply-worker"
python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt

echo "[ec2] Writing systemd units..."
sudo tee /etc/systemd/system/jobnova-xvfb.service >/dev/null <<EOF
[Unit]
Description=JobNova Xvfb display :99
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/Xvfb :99 -screen 0 1920x1080x24
Restart=always

[Install]
WantedBy=multi-user.target
EOF

echo "[ec2] Setting VNC password for review access..."
mkdir -p "$USER_HOME/.vnc"
if [[ ! -f "$USER_HOME/.vnc/passwd" ]]; then
  read -rsp "Set a VNC password (used to view/submit filled forms): " VNC_PASS
  echo
  x11vnc -storepasswd "$VNC_PASS" "$USER_HOME/.vnc/passwd"
fi

sudo tee /etc/systemd/system/jobnova-vnc.service >/dev/null <<EOF
[Unit]
Description=JobNova VNC viewer for review (display :99)
After=network.target jobnova-xvfb.service
Requires=jobnova-xvfb.service

[Service]
Type=simple
User=$(whoami)
ExecStart=/usr/bin/x11vnc -display :99 -rfbauth $USER_HOME/.vnc/passwd -forever -shared -rfbport 5900
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/jobnova-apply-worker.service >/dev/null <<EOF
[Unit]
Description=JobNova Lever apply worker
After=network.target jobnova-xvfb.service
Requires=jobnova-xvfb.service

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$ROOT/services/apply-worker
Environment=DISPLAY=:99
Environment=API_URL=${API_URL:-http://127.0.0.1:8000}
Environment=APPLY_WORKER_SECRET=${APPLY_WORKER_SECRET:-change-me}
Environment=EXTENSION_PATH=$USER_HOME/jobnova-extension
Environment=CHROME_PROFILE=$USER_HOME/chrome-profile
ExecStart=$ROOT/services/apply-worker/.venv/bin/python $ROOT/services/apply-worker/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable jobnova-xvfb jobnova-vnc jobnova-apply-worker

echo "[ec2] Done. Set APPLY_WORKER_SECRET in .env and API_URL, then:"
echo "  sudo systemctl start jobnova-xvfb"
echo "  sudo systemctl start jobnova-vnc"
echo "  sudo systemctl start jobnova-apply-worker"
echo "  sudo systemctl status jobnova-apply-worker"
echo ""
echo "[ec2] To review/submit filled forms, open an SSH tunnel from your machine:"
echo "  ssh -L 5900:localhost:5900 ec2-user@<EC2_PUBLIC_IP>"
echo "  then connect a VNC viewer to localhost:5900 (port forwarded over SSH — not exposed publicly)"
