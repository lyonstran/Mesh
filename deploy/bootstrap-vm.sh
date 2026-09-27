#!/usr/bin/env bash
# One-time setup for a fresh Ubuntu VM (tested target: Ubuntu 24.04 LTS on Vultr). Run once, as root:
#   sudo ./deploy/bootstrap-vm.sh
# It installs Docker, opens only SSH/HTTP/HTTPS in the firewall, and adds a small swap file so builds
# don't run out of memory on a 2 GB machine. Safe to run again.
set -euo pipefail

die() { echo "ERROR: $*" >&2; exit 1; }
[ "$(id -u)" -eq 0 ] || die "Run this with sudo."

echo "==> Installing base packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y ca-certificates curl git ufw

echo "==> Installing Docker (official install script from get.docker.com)"
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi
systemctl enable --now docker
docker compose version >/dev/null 2>&1 || die "Docker Compose plugin is missing after install."

echo "==> Swap file (2 GB) if the machine has none"
if [ -z "$(swapon --show --noheadings)" ]; then
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
else
  echo "    swap already present, skipping"
fi

echo "==> Firewall: allow SSH, HTTP, HTTPS (and HTTP/3 over UDP 443)"
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 443/udp
ufw --force enable

if [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != "root" ]; then
  usermod -aG docker "$SUDO_USER"
  echo "==> Added $SUDO_USER to the docker group. Log out and back in before running ./deploy/deploy.sh."
fi

echo
echo "Done. Next: create .env (cp deploy/env.production.example .env), then run ./deploy/deploy.sh"
