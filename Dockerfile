# ---------- Stage 1: build TailwindCSS ----------
FROM node:20-alpine AS assets
WORKDIR /app
COPY package.json tailwind.config.js ./
RUN npm install --no-audit --no-fund
COPY static ./static
COPY templates ./templates
COPY crm ./crm
RUN npm run build:css

# ---------- Stage 2: Django + Gunicorn ----------
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

RUN useradd --create-home --uid 1000 app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY --chown=app:app . .
COPY --from=assets --chown=app:app /app/static/css/app.css ./static/css/app.css

# collectstatic ตอน build (ใช้ key ชั่วคราว ไม่ใช่ key จริง)
RUN DJANGO_SECRET_KEY=build-only-placeholder-key-not-used-at-runtime-xxxxxxxx \
    python manage.py collectstatic --noinput \
 && chmod +x entrypoint.sh

USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz/').status==200 else 1)"

ENTRYPOINT ["./entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application"]
