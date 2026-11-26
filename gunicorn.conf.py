# Gunicorn โหลดไฟล์นี้อัตโนมัติเมื่อรันจากโฟลเดอร์โปรเจกต์
import multiprocessing
import os

bind = os.environ.get("GUNICORN_BIND", "0.0.0.0:8000")
# สูตรแนะนำ: (2 x CPU) + 1 — VPS 1 vCPU ใช้ 3 workers ก็พอ
workers = int(os.environ.get("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "60"))
accesslog = "-"
errorlog = "-"
forwarded_allow_ips = "*"  # เชื่อ X-Forwarded-* จาก Nginx (gunicorn ไม่เปิดพอร์ตออกนอกเครื่อง)
