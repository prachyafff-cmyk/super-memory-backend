#!/bin/sh
set -e

echo "→ Running migrations"
python manage.py migrate --noinput

# สร้าง superuser ครั้งแรกอัตโนมัติ ถ้าตั้ง DJANGO_SUPERUSER_USERNAME/PASSWORD ไว้ใน .env
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
  python manage.py createsuperuser --noinput 2>/dev/null \
    && echo "→ Superuser '$DJANGO_SUPERUSER_USERNAME' created" \
    || echo "→ Superuser already exists"
fi

echo "→ Starting: $*"
exec "$@"
