#!/usr/bin/env bash
set -euo pipefail

VM="stvaldivia"

echo "=== PUSH A GITHUB ==="
git push

echo "=== DEPLOY EN VM: $VM ==="
gcloud compute ssh "$VM" --command '
set -euo pipefail

echo ">> Entrando a /var/www/stvaldivia"
cd /var/www/stvaldivia

echo ">> git pull"
sudo -u deploy git pull

echo ">> pip install"
sudo -u deploy /var/www/stvaldivia/venv/bin/pip install -r requirements.txt

echo ">> restart gunicorn"
sudo -u deploy pkill -f "gunicorn.*--bind 127.0.0.1:5001" || true

sudo -u deploy /var/www/stvaldivia/venv/bin/gunicorn \
  --pythonpath /var/www/stvaldivia \
  --bind 127.0.0.1:5001 \
  --workers 4 \
  --worker-class eventlet \
  --timeout 30 \
  --access-logfile /var/www/stvaldivia/logs/access.log \
  --error-logfile /var/www/stvaldivia/logs/error.log \
  --daemon app:app

echo ">> healthcheck"
curl -fsS http://127.0.0.1:5001 >/dev/null

echo "=== DEPLOY OK ==="
'
