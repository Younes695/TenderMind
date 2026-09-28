#!/usr/bin/env bash
# TenderMind — one-command install on a fresh Ubuntu 22.04/24.04 server
# (Oracle Cloud "Always Free" Ampere A1 ARM: 4 OCPU / 24 GB works, CPU-only).
#
#   git clone <your repo> tendermind && cd tendermind
#   sudo DOMAIN=tenders.example.com EMAIL=you@example.com ./deploy/oracle-setup.sh
#
# DOMAIN must already point (DNS A record) at this server's public IP.
# Caddy gets a free HTTPS certificate automatically. Re-running is safe.
set -euo pipefail

: "${DOMAIN:?set DOMAIN=your.domain}"
: "${EMAIL:?set EMAIL=you@example.com for HTTPS certificate notices}"
cd "$(dirname "$0")/.."

echo "==> Docker"
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sh
fi
systemctl enable --now docker

echo "==> Firewall (Oracle Ubuntu images block 80/443 in iptables by default)"
for p in 80 443; do
  iptables -C INPUT -p tcp --dport "$p" -j ACCEPT 2>/dev/null || iptables -I INPUT 6 -p tcp --dport "$p" -j ACCEPT
done
command -v netfilter-persistent >/dev/null && netfilter-persistent save || true
echo "    Also open TCP 80 and 443 in the VCN Security List (Oracle console)."

echo "==> .env"
if [ ! -f .env ]; then
  cp .env.example .env
  secret=$(openssl rand -hex 32)
  sed -i "s/^TENDERMIND_SESSION_SECRET=.*/TENDERMIND_SESSION_SECRET=${secret}/" .env
fi
grep -q '^TENDERMIND_CORS_ORIGINS=' .env || echo "TENDERMIND_CORS_ORIGINS=https://${DOMAIN}" >> .env
if ! command -v nvidia-smi >/dev/null; then
  # CPU-only: the second (escalation) model would only slow processing down;
  # requirements it cannot settle go through the Stage 5K rule fallback instead.
  grep -q '^TENDERMIND_ESCALATION_MODEL=' .env || echo "TENDERMIND_ESCALATION_MODEL=off" >> .env
fi

echo "==> Start"
export DOMAIN EMAIL
docker compose -f docker-compose.yml -f deploy/docker-compose.https.yml up -d --build

echo "==> Waiting for https://${DOMAIN}/health"
for i in $(seq 1 90); do
  if curl -fsS "https://${DOMAIN}/health" >/dev/null 2>&1; then
    echo "TenderMind is live: https://${DOMAIN}"
    exit 0
  fi
  sleep 20
done
echo "Not healthy yet (first start downloads the AI model). Check: docker compose logs -f app caddy" >&2
exit 1
