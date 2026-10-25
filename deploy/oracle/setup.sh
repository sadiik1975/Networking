#!/usr/bin/env bash
# Run on a fresh Ubuntu Oracle Cloud VM:  DOMAIN=yourname.duckdns.org bash setup.sh
set -euo pipefail

: "${DOMAIN:?Set DOMAIN, e.g. DOMAIN=yourname.duckdns.org}"
APP_DIR="$HOME/Networking"

sudo apt-get update
sudo apt-get install -y python3-venv python3-pip git caddy

[ -d "$APP_DIR" ] || git clone https://github.com/sadiik1975/Networking.git "$APP_DIR"
cd "$APP_DIR"
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

if [ ! -f .env ]; then
  {
    echo "DATABASE_URL=sqlite:///$APP_DIR/leads.db"
    echo "DISPATCH_API_KEY=$(openssl rand -hex 24)"
    echo "MCP_API_KEY=$(openssl rand -hex 24)"
    echo "# TAVILY_API_KEY="
    echo "# TELEGRAM_BOT_TOKEN="
    echo "# TELEGRAM_CHAT_ID="
  } > .env
  chmod 600 .env
fi

sed -e "s|__USER__|$USER|g" -e "s|__APP_DIR__|$APP_DIR|g" deploy/oracle/networking.service \
  | sudo tee /etc/systemd/system/networking.service >/dev/null
sed "s|__DOMAIN__|$DOMAIN|g" deploy/oracle/Caddyfile | sudo tee /etc/caddy/Caddyfile >/dev/null

# Ubuntu images on Oracle ship with iptables rules that block 80/443.
sudo iptables -I INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT
sudo sh -c 'iptables-save > /etc/iptables/rules.v4' 2>/dev/null || sudo apt-get install -y iptables-persistent

sudo systemctl daemon-reload
sudo systemctl enable --now networking
sudo systemctl restart caddy

echo "Done. Health: https://$DOMAIN/health"
echo "Your MCP key: $(grep '^MCP_API_KEY=' .env | cut -d= -f2)"
