#!/usr/bin/env bash
# อัปเดตเวอร์ชันใหม่บนเซิร์ฟเวอร์:  ./deploy/deploy.sh
set -euo pipefail
cd "$(dirname "$0")/.."

echo "→ Pull latest code"
git pull --ff-only

echo "→ Backup database before deploy"
mkdir -p backups
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > "backups/db-$(date +%Y%m%d-%H%M%S).sql.gz"

echo "→ Build & restart"
docker compose up -d --build

echo "→ Clean old images"
docker image prune -f

echo "→ Health check"
for i in $(seq 1 20); do
  if curl -fsS http://127.0.0.1:8000/healthz/ >/dev/null; then
    echo "✓ Deploy สำเร็จ"; exit 0
  fi
  sleep 2
done
echo "✗ Health check ไม่ผ่าน — ดู log: docker compose logs --tail=100 web"; exit 1
