"""สร้างข้อมูลตัวอย่าง: python manage.py seed_demo [--reset]"""
import random
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from crm.models import Booking, Guest, Interaction, Payment, Room, RoomType

ROOM_TYPES = [
    ("Garden Villa", 2500, 2, "วิลล่าวิวสวน เตียงคิงไซซ์"),
    ("Family Bungalow", 3800, 5, "บังกะโลครอบครัว 2 ห้องนอน"),
    ("Pool Villa", 4500, 3, "วิลล่าพร้อมสระว่ายน้ำส่วนตัว"),
    ("Beachfront Suite", 6500, 4, "สวีทติดชายหาด ระเบียงชมพระอาทิตย์ตก"),
]
LAYOUT = {  # โซน: [(เลขห้อง, ประเภท)]
    1: [(f"G{i:02d}", "Garden Villa") for i in range(1, 7)] + [(f"F{i:02d}", "Family Bungalow") for i in range(1, 4)],
    2: [(f"P{i:02d}", "Pool Villa") for i in range(1, 6)],
    3: [(f"B{i:02d}", "Beachfront Suite") for i in range(1, 5)],
}
GUESTS = [
    ("สมชาย", "ใจดี", "ไทย"), ("สุดารัตน์", "แก้วมณี", "ไทย"), ("วิภาวดี", "ศรีสุข", "ไทย"),
    ("ณัฐพล", "บุญมา", "ไทย"), ("ปิยะนุช", "ทองคำ", "ไทย"), ("อนันต์", "วงศ์ใหญ่", "ไทย"),
    ("กมลชนก", "รัตนา", "ไทย"), ("ธนากร", "สายทอง", "ไทย"), ("พิมพ์ชนก", "อินทร์แก้ว", "ไทย"),
    ("ชยพล", "มั่นคง", "ไทย"), ("Ahmad", "Rahman", "มาเลเซีย"), ("Siti", "Aminah", "มาเลเซีย"),
    ("Wei Ling", "Tan", "สิงคโปร์"), ("Daniel", "Lim", "สิงคโปร์"), ("Emma", "Schmidt", "เยอรมนี"),
    ("Lukas", "Weber", "เยอรมนี"), ("Olivia", "Brown", "อังกฤษ"), ("James", "Wilson", "ออสเตรเลีย"),
    ("Yuki", "Tanaka", "ญี่ปุ่น"), ("Min-jun", "Kim", "เกาหลีใต้"), ("Li", "Wang", "จีน"),
    ("Sophie", "Martin", "ฝรั่งเศส"), ("Arjun", "Mehta", "อินเดีย"), ("Nur", "Hidayah", "อินโดนีเซีย"),
    ("Lars", "Johansson", "สวีเดน"),
]
REQUESTS = ["", "", "", "ขอเตียงเสริม", "ฉลองวันครบรอบ ขอจัดดอกไม้", "มาถึงดึก ประมาณ 22:00",
            "ไม่ทานเนื้อวัว", "ขอห้องใกล้สระ", "ขอรถรับจากสนามบินหาดใหญ่"]
SUBJECTS = ["สอบถามโปรโมชันช่วงปีใหม่", "ขอใบเสร็จ/ใบกำกับภาษี", "ติดตามรีวิวหลังเข้าพัก",
            "เสนอแพ็กเกจสปา", "สอบถามห้องสำหรับกรุ๊ป 10 คน", "แจ้งเปลี่ยนวันเข้าพัก"]


class Command(BaseCommand):
    help = "สร้างข้อมูลตัวอย่าง (ประเภทห้อง ห้อง ลูกค้า การจอง การชำระเงิน)"

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="ลบข้อมูล CRM เดิมก่อน")
        parser.add_argument("--seed", type=int, default=42)

    @transaction.atomic
    def handle(self, *args, **opts):
        rng = random.Random(opts["seed"])
        if opts["reset"]:
            for model in (Payment, Interaction, Booking, Room, RoomType, Guest):
                model.objects.all().delete()
        elif Room.objects.exists():
            self.stdout.write(self.style.WARNING("มีข้อมูลอยู่แล้ว — ใช้ --reset หากต้องการสร้างใหม่"))
            return

        types = {
            name: RoomType.objects.create(name=name, base_price=Decimal(price), capacity=cap, description=desc)
            for name, price, cap, desc in ROOM_TYPES
        }
        rooms = [
            Room.objects.create(number=num, room_type=types[t], floor=floor)
            for floor, items in LAYOUT.items() for num, t in items
        ]

        guests = []
        for first, last, nat in GUESTS:
            slug = (last or first).lower().replace(" ", "")
            guests.append(Guest.objects.create(
                first_name=first, last_name=last, nationality=nat,
                phone=f"08{rng.randint(10000000, 99999999)}",
                email=f"{slug}{rng.randint(1, 99)}@example.com",
                line_id=f"{slug}{rng.randint(10, 99)}" if nat == "ไทย" else "",
                tier=rng.choices(Guest.Tier.values, weights=[60, 20, 13, 7])[0],
                marketing_opt_in=rng.random() < 0.6,
            ))

        today = timezone.localdate()
        tz = timezone.get_current_timezone()
        S = Booking.Status
        for room in rooms:
            cursor = today - timedelta(days=45)
            while cursor < today + timedelta(days=30):
                cursor += timedelta(days=rng.randint(0, 7))
                nights = rng.randint(1, 5)
                ci, co = cursor, cursor + timedelta(days=nights)
                if co == today and rng.random() < 0.5:
                    status = S.CHECKED_IN  # รอเช็คเอาท์วันนี้
                elif co <= today:
                    status = S.CANCELLED if rng.random() < 0.08 else S.CHECKED_OUT
                elif ci == today:
                    status = S.CONFIRMED  # รอเช็คอินวันนี้
                elif ci < today:
                    status = S.CHECKED_IN
                else:
                    status = rng.choice([S.CONFIRMED, S.CONFIRMED, S.PENDING])
                guest = rng.choice(guests)
                booking = Booking.objects.create(
                    guest=guest, room=room, check_in=ci, check_out=co, status=status,
                    adults=min(2, room.room_type.capacity), source=rng.choice(Booking.Source.values),
                    special_requests=rng.choice(REQUESTS),
                )
                paid_on = lambda d: timezone.make_aware(datetime.combine(d, time(rng.randint(9, 20), rng.randint(0, 59))), tz)
                if status == S.CHECKED_OUT:
                    Payment.objects.create(booking=booking, amount=booking.total_amount,
                                           method=rng.choice(Payment.Method.values), paid_at=paid_on(co))
                elif status == S.CHECKED_IN:
                    Payment.objects.create(booking=booking, amount=booking.total_amount / 2,
                                           method=Payment.Method.TRANSFER, paid_at=paid_on(ci))
                    room.status = Room.Status.OCCUPIED
                elif status == S.CONFIRMED and rng.random() < 0.5:
                    Payment.objects.create(booking=booking, amount=(booking.total_amount * Decimal("0.3")).quantize(Decimal("1")),
                                           method=Payment.Method.PROMPTPAY, paid_at=paid_on(min(today, ci)))
                cursor = co
            if room.status != Room.Status.OCCUPIED and room.bookings.filter(check_out=today, status=S.CHECKED_OUT).exists():
                room.status = Room.Status.CLEANING
            room.save()
        rooms[-1].status, rooms[-1].notes = Room.Status.MAINTENANCE, "แอร์มีปัญหา รอช่าง"
        rooms[-1].save()

        for guest in rng.sample(guests, 12):
            Interaction.objects.create(
                guest=guest, channel=rng.choice(Interaction.Channel.values), subject=rng.choice(SUBJECTS),
                note="ลูกค้าสนใจ ให้ติดต่อกลับพร้อมใบเสนอราคา",
                follow_up_date=today + timedelta(days=rng.randint(-2, 6)) if rng.random() < 0.7 else None,
            )

        self.stdout.write(self.style.SUCCESS(
            f"สร้างข้อมูลแล้ว: ห้อง {len(rooms)} · ลูกค้า {len(guests)} · การจอง {Booking.objects.count()} · "
            f"ชำระเงิน {Payment.objects.count()}"
        ))
