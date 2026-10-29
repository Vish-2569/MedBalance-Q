#!/usr/bin/env bash
# MedBalance-Q — AWS EC2 standby setup
# Run as root on a fresh Ubuntu 24.04 t3.xlarge instance.
# Prerequisites: /tmp/medbal.env with all secrets pre-staged.
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/YOUR_ORG/MedBalance-Q.git}"
REPO_BRANCH="${REPO_BRANCH:-main}"
INSTALL_DIR="/opt/medbalance"
ENV_SOURCE="/tmp/medbal.env"

log() { echo ">>> [$(date +%H:%M:%S)] $*"; }

# ── Pre-checks ───────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
  echo "ERROR: Run as root (sudo bash $0)" >&2
  exit 1
fi

if [[ ! -f "$ENV_SOURCE" ]]; then
  echo "ERROR: $ENV_SOURCE not found. Upload it first:" >&2
  echo "  scp .env ubuntu@<ip>:/tmp/medbal.env" >&2
  exit 1
fi

# ── Install Docker ───────────────────────────────────────────────
log "Installing Docker..."
apt-get update -qq
apt-get install -y -qq ca-certificates curl gnupg lsb-release make git

install_docker() {
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
    https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -qq
  apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin
}

for attempt in 1 2 3; do
  if install_docker; then
    log "Docker installed on attempt $attempt"
    break
  fi
  log "Docker install attempt $attempt failed, retrying in 5s..."
  sleep 5
  if [[ $attempt -eq 3 ]]; then
    echo "ERROR: Docker install failed after 3 attempts" >&2
    exit 1
  fi
done

systemctl enable --now docker
docker version --format '{{.Server.Version}}' >/dev/null 2>&1 \
  || { echo "ERROR: Docker daemon not running" >&2; exit 1; }

# ── Clone repo ───────────────────────────────────────────────────
log "Cloning repo..."
rm -rf "$INSTALL_DIR"
git clone --depth 1 --branch "$REPO_BRANCH" "$REPO_URL" "$INSTALL_DIR"
cd "$INSTALL_DIR"

# ── Stage .env (no secrets in repo) ──────────────────────────────
log "Copying .env..."
cp "$ENV_SOURCE" .env
chmod 600 .env

# ── Firewall ─────────────────────────────────────────────────────
log "Configuring firewall..."
if command -v ufw >/dev/null 2>&1; then
  ufw allow 22/tcp   >/dev/null 2>&1 || true
  ufw allow 8080/tcp >/dev/null 2>&1 || true
  ufw --force enable >/dev/null 2>&1 || true
fi

# ── Build & launch ───────────────────────────────────────────────
log "Building images (this takes 2-4 minutes on first run)..."
make demo

# ── Print result ─────────────────────────────────────────────────
PUBLIC_IP=$(curl -s --max-time 3 http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || hostname -I | awk '{print $1}')
echo ""
echo "============================================================"
echo "  MedBalance-Q is running"
echo "  URL: http://${PUBLIC_IP}:8080"
echo "============================================================"
echo ""
