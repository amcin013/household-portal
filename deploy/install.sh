#!/usr/bin/env bash
# First-time setup on a Debian/Ubuntu box.
#
#   git clone <this repo> /opt/household-portal
#   cd /opt/household-portal
#   sudo bash deploy/install.sh
#
# Safe to run again later - it skips anything already done.

set -euo pipefail

APP_DIR="${APP_DIR:-/opt/household-portal}"
APP_USER="${APP_USER:-portal}"

say() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }

if [[ $EUID -ne 0 ]]; then
  echo "Run this with sudo." >&2
  exit 1
fi

say "Checking Python"
if ! command -v python3 >/dev/null; then
  apt-get update && apt-get install -y python3 python3-venv python3-pip
fi
python3 --version

say "Creating the service account"
if ! id "$APP_USER" >/dev/null 2>&1; then
  useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"
  echo "created user $APP_USER"
else
  echo "user $APP_USER already exists"
fi

say "Setting up the virtualenv"
cd "$APP_DIR"
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt
echo "dependencies installed"

say "Preparing the config"
if [[ ! -f .env ]]; then
  cp .env.example .env
  SECRET=$(.venv/bin/python -c "import secrets;print(secrets.token_hex(32))")
  sed -i "s/^SECRET_KEY=.*/SECRET_KEY=${SECRET}/" .env
  echo "wrote .env with a fresh SECRET_KEY - open it and fill in the rest"
else
  echo ".env already exists, leaving it alone"
fi

say "Creating the database"
mkdir -p instance
.venv/bin/python -c "from portal import create_app; create_app()"
echo "database ready at $APP_DIR/instance/portal.db"

say "Loading starter content"
.venv/bin/flask --app wsgi seed || true

say "Fixing ownership"
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

say "Installing the service"
cp deploy/household-portal.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable household-portal
systemctl restart household-portal
sleep 2
systemctl --no-pager status household-portal || true

cat <<'DONE'

==> Done.

Next:
  1. Edit /opt/household-portal/.env
       - set ALLOWED_EMAILS to the Google accounts that should get in
       - either add GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET,
         or set AUTH_MODE=local and a LOCAL_PASSWORD to start on the LAN
  2. sudo systemctl restart household-portal
  3. Open http://<this-machine>:8000  (or put nginx in front - see
     deploy/nginx.conf.example)

The first person to sign in becomes the admin.

Back up /opt/household-portal/instance/portal.db - that single file is
everything.
DONE
