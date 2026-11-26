# 🏝️ Resort CRM — ระบบบริหารลูกค้าสัมพันธ์รีสอร์ต

โปรเจกต์ตัวอย่างสำหรับฝึก **Deploy เว็บ Django ขึ้น Cloud Server จริง**
Stack: **Django 5.2 · Vanilla JavaScript · TailwindCSS 3 · PostgreSQL 16 · Gunicorn · Nginx · Docker**

![Dashboard](docs/screenshot-dashboard.png)

## ฟีเจอร์

| โมดูล | รายละเอียด |
|---|---|
| แดชบอร์ด | อัตราเข้าพัก, เช็คอิน/เช็คเอาท์วันนี้, รายรับเดือนนี้, กราฟรายรับ 14 วัน (JS + API), งานติดตามลูกค้า |
| ลูกค้า (CRM) | ข้อมูลลูกค้า, ระดับสมาชิก (Regular/Silver/Gold/VIP), ประวัติการเข้าพัก, ยอดใช้จ่ายรวม, **บันทึกการติดต่อ + นัดติดตาม** |
| การจอง | สร้าง/แก้ไขการจอง, **ตรวจห้องว่างแบบ realtime** ในฟอร์ม, กันจองซ้อนและเกินความจุ, ยืนยัน → เช็คอิน → เช็คเอาท์ / ยกเลิก |
| ห้องพัก | ผังห้องแยกโซน, เปลี่ยนสถานะห้อง (ว่าง/มีผู้พัก/รอทำความสะอาด/ซ่อม) ผ่าน API โดยไม่ต้อง reload |
| การเงิน | รับชำระหลายครั้งต่อการจอง (เงินสด/โอน/พร้อมเพย์/บัตร/OTA), คำนวณยอดค้างอัตโนมัติ |
| Ops | `/healthz/` health check, Django Admin, ข้อมูลตัวอย่าง `seed_demo`, เทสต์ 13 เคส, GitHub Actions CI |

## โครงสร้างโปรเจกต์

```
resort-crm/
├── config/              # settings (อ่านค่าจาก .env), urls, wsgi
├── crm/                 # แอปหลัก: models, views, forms, API, templates, tests
│   └── management/commands/seed_demo.py
├── templates/           # base.html, หน้า login
├── static/
│   ├── src/input.css    # ต้นฉบับ Tailwind (+ component classes)
│   ├── css/app.css      # ไฟล์ที่ build แล้ว (สร้างด้วย npm run build:css)
│   └── js/app.js        # JavaScript ทั้งหมด (ไม่มี framework)
├── deploy/
│   ├── nginx/resort-crm.conf   # Nginx reverse proxy
│   ├── resort-crm.service      # systemd (ทางเลือกแบบไม่ใช้ Docker)
│   └── deploy.sh               # สคริปต์อัปเดตเวอร์ชัน (backup DB → build → health check)
├── Dockerfile           # multi-stage: Node build Tailwind → Python runtime
├── docker-compose.yml   # web (gunicorn) + db (postgres)
├── entrypoint.sh        # migrate + สร้าง superuser อัตโนมัติ
├── gunicorn.conf.py
└── .env.example
```

---

## 1) รันบนเครื่องตัวเอง (Development)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
npm install && npm run build:css        # หรือ npm run watch:css ระหว่างแก้ UI

echo "DJANGO_DEBUG=True" > .env         # dev ใช้ SQLite อัตโนมัติ
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_demo              # ข้อมูลตัวอย่าง (ห้อง 18, ลูกค้า 25, การจองย้อนหลัง/ล่วงหน้า)
python manage.py runserver
```
เปิด http://127.0.0.1:8000 → login

รันเทสต์: `DJANGO_DEBUG=True python manage.py test`

---

## 2) Deploy ขึ้น Cloud Server ด้วย Docker (แนะนำ)

ใช้ได้กับ VPS ทุกเจ้า (DigitalOcean, AWS Lightsail/EC2, GCP, Vultr, Linode, Hetzner ฯลฯ)
**สเปกขั้นต่ำ:** Ubuntu 22.04/24.04 · 1 vCPU · RAM 1 GB (แนะนำ 2 GB) · โดเมนที่ชี้ A record มาที่ IP ของเซิร์ฟเวอร์

### สถาปัตยกรรม
```
Internet ──443/80──▶ Nginx (บน host + Let's Encrypt SSL)
                       │ proxy_pass 127.0.0.1:8000
                       ▼
              ┌─ Docker Compose ───────────────┐
              │  web: Gunicorn + Django        │
              │       (WhiteNoise เสิร์ฟ static) │
              │  db : PostgreSQL 16 (volume)   │
              └────────────────────────────────┘
```

### ขั้นตอนที่ 1 — เตรียมเซิร์ฟเวอร์
```bash
ssh root@YOUR_SERVER_IP

# สร้าง user สำหรับ deploy (ไม่ใช้ root ทำงานประจำ)
adduser deploy && usermod -aG sudo deploy
rsync --archive --chown=deploy:deploy ~/.ssh /home/deploy   # คัดลอก SSH key
su - deploy

# อัปเดตระบบ + Firewall
sudo apt update && sudo apt upgrade -y
sudo ufw allow OpenSSH && sudo ufw allow 'Nginx Full' 2>/dev/null || sudo ufw allow 80,443/tcp
sudo ufw enable

# (สำหรับ RAM 1 GB) เพิ่ม swap 2 GB กัน build ล่ม
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### ขั้นตอนที่ 2 — ติดตั้ง Docker และ Nginx
```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER && newgrp docker
sudo apt install -y nginx certbot python3-certbot-nginx git
```

### ขั้นตอนที่ 3 — นำโค้ดขึ้นเซิร์ฟเวอร์
```bash
sudo mkdir -p /srv/resort-crm && sudo chown $USER /srv/resort-crm
git clone https://github.com/YOUR_USER/resort-crm.git /srv/resort-crm
# (หรืออัปโหลด zip: scp resort-crm.zip deploy@IP:/srv/ แล้ว unzip)
cd /srv/resort-crm
```

### ขั้นตอนที่ 4 — ตั้งค่า .env
```bash
cp .env.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(50))"   # → DJANGO_SECRET_KEY
openssl rand -hex 24                                             # → POSTGRES_PASSWORD
nano .env
```
แก้อย่างน้อย: `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `POSTGRES_PASSWORD`, `DJANGO_SUPERUSER_PASSWORD`
```bash
chmod 600 .env
```

### ขั้นตอนที่ 5 — Build และ Start
```bash
docker compose up -d --build
docker compose ps                       # web ต้องเป็น healthy
docker compose logs -f web              # ดู log (Ctrl+C ออก)
curl http://127.0.0.1:8000/healthz/     # → ok

# (ถ้าต้องการ) ใส่ข้อมูลตัวอย่าง
docker compose exec web python manage.py seed_demo
```

### ขั้นตอนที่ 6 — Nginx + HTTPS (Let's Encrypt)
```bash
sudo cp deploy/nginx/resort-crm.conf /etc/nginx/sites-available/resort-crm
sudo sed -i 's/crm.example.com/crm.yourdomain.com/' /etc/nginx/sites-available/resort-crm
sudo ln -s /etc/nginx/sites-available/resort-crm /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

sudo certbot --nginx -d crm.yourdomain.com --redirect -m you@email.com --agree-tos
sudo certbot renew --dry-run            # ทดสอบต่ออายุอัตโนมัติ
```
เปิด **https://crm.yourdomain.com** → login ด้วย superuser ที่ตั้งใน `.env` ✅

> หลัง HTTPS ทำงานเสถียรแล้ว ตั้ง `DJANGO_SECURE_HSTS_SECONDS=31536000` ใน `.env` แล้ว `docker compose up -d`

---

## 3) อัปเดตเวอร์ชันใหม่
```bash
cd /srv/resort-crm && ./deploy/deploy.sh
```
สคริปต์จะ: `git pull` → backup ฐานข้อมูลลง `backups/` → build image ใหม่ → restart → ลบ image เก่า → ตรวจ `/healthz/`
(migration รันอัตโนมัติใน `entrypoint.sh`)

## 4) Backup / Restore ฐานข้อมูล
```bash
# Backup
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > backup.sql.gz
# Restore
gunzip -c backup.sql.gz | docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" "$POSTGRES_DB"'
```
ตั้ง cron backup ทุกคืน (`crontab -e`):
```
0 3 * * * cd /srv/resort-crm && docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > backups/db-$(date +\%F).sql.gz && find backups -mtime +14 -delete
```

---

## 5) ทางเลือก: Deploy แบบไม่ใช้ Docker (systemd)
```bash
sudo apt install -y python3-venv postgresql nginx
sudo -u postgres psql -c "CREATE USER resort WITH PASSWORD 'xxx';" -c "CREATE DATABASE resort_crm OWNER resort;"
sudo adduser --system --group resort   # user สำหรับรัน gunicorn
cd /srv/resort-crm
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
# ใน .env ตั้ง DATABASE_URL=postgres://resort:xxx@127.0.0.1:5432/resort_crm
.venv/bin/python manage.py migrate && .venv/bin/python manage.py collectstatic --noinput
.venv/bin/python manage.py createsuperuser
sudo chown -R resort:www-data /srv/resort-crm
sudo cp deploy/resort-crm.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now resort-crm
```
จากนั้นทำขั้นตอนที่ 6 (Nginx + Certbot) เหมือนกัน
> ไม่มี Node บนเซิร์ฟเวอร์? build CSS บนเครื่องตัวเองแล้ว commit `static/css/app.css` ขึ้นไปด้วย

---

## Security checklist ก่อนเปิดใช้งานจริง
- [ ] `DJANGO_DEBUG=False` และ `DJANGO_SECRET_KEY` สุ่มใหม่ (ระบบจะไม่ยอม start ถ้า key อ่อน)
- [ ] `.env` เป็น `chmod 600` และไม่ถูก commit ขึ้น Git
- [ ] Port 8000 / 5432 **ไม่**เปิดออกอินเทอร์เน็ต (compose bind ไว้ที่ 127.0.0.1 แล้ว, ufw เปิดแค่ 22/80/443)
- [ ] HTTPS ทำงาน + `DJANGO_SECURE_COOKIES=True`
- [ ] รัน `docker compose exec web python manage.py check --deploy`
- [ ] ตั้ง backup อัตโนมัติ และทดลอง restore อย่างน้อย 1 ครั้ง
- [ ] SSH: ปิด password login (`PasswordAuthentication no`) ใช้ key อย่างเดียว, พิจารณาติดตั้ง `fail2ban`
- [ ] สร้าง user พนักงานแยกคน (Admin → Users) ไม่ใช้บัญชี superuser ร่วมกัน

## แก้ปัญหาที่พบบ่อย
| อาการ | สาเหตุ / วิธีแก้ |
|---|---|
| `400 Bad Request` | โดเมนไม่อยู่ใน `DJANGO_ALLOWED_HOSTS` |
| `403 CSRF verification failed` | ใส่ `https://โดเมน` ใน `DJANGO_CSRF_TRUSTED_ORIGINS` |
| Login แล้วเด้งกลับหน้า login | เปิดผ่าน http:// แต่ `DJANGO_SECURE_COOKIES=True` → ติด SSL ก่อน หรือตั้ง False ชั่วคราว |
| `502 Bad Gateway` | container web ไม่ทำงาน → `docker compose logs web` |
| CSS ไม่โหลด | ลืม build CSS / collectstatic → `docker compose up -d --build` |
| Build ล่มบน RAM 1 GB | เพิ่ม swap (ขั้นตอนที่ 1) |

## API ภายใน (ใช้โดย `static/js/app.js`, ต้อง login)
| Method | Endpoint | ใช้ทำอะไร |
|---|---|---|
| GET | `/api/revenue/?days=14` | รายรับรายวันสำหรับกราฟ |
| GET | `/api/availability/?check_in=YYYY-MM-DD&check_out=YYYY-MM-DD[&booking=id]` | ห้องที่ว่างในช่วงวันที่ |
| POST | `/api/rooms/<id>/status/` body `{"status":"cleaning"}` + header `X-CSRFToken` | เปลี่ยนสถานะห้อง |
| GET | `/healthz/` | health check (ไม่ต้อง login) |
