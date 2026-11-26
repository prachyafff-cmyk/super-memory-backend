from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum
from django.urls import reverse


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField("สร้างเมื่อ", auto_now_add=True)
    updated_at = models.DateTimeField("แก้ไขเมื่อ", auto_now=True)

    class Meta:
        abstract = True


class Guest(TimeStampedModel):
    class Tier(models.TextChoices):
        REGULAR = "regular", "ทั่วไป"
        SILVER = "silver", "Silver"
        GOLD = "gold", "Gold"
        VIP = "vip", "VIP"

    first_name = models.CharField("ชื่อ", max_length=100)
    last_name = models.CharField("นามสกุล", max_length=100, blank=True)
    email = models.EmailField("อีเมล", blank=True)
    phone = models.CharField("โทรศัพท์", max_length=30, blank=True)
    line_id = models.CharField("LINE ID", max_length=50, blank=True)
    nationality = models.CharField("สัญชาติ", max_length=50, blank=True, default="ไทย")
    tier = models.CharField("ระดับสมาชิก", max_length=10, choices=Tier.choices, default=Tier.REGULAR)
    birthday = models.DateField("วันเกิด", null=True, blank=True)
    marketing_opt_in = models.BooleanField("ยินยอมรับข่าวสาร/โปรโมชัน", default=False)
    notes = models.TextField("ความชอบ / บันทึก", blank=True, help_text="เช่น แพ้อาหารทะเล, ชอบห้องชั้นบน")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "ลูกค้า"
        verbose_name_plural = "ลูกค้า"

    def __str__(self):
        return self.full_name

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def get_absolute_url(self):
        return reverse("crm:guest_detail", args=[self.pk])


class RoomType(models.Model):
    name = models.CharField("ชื่อประเภทห้อง", max_length=100, unique=True)
    base_price = models.DecimalField("ราคาต่อคืน (บาท)", max_digits=10, decimal_places=2)
    capacity = models.PositiveSmallIntegerField("รองรับ (คน)", default=2)
    description = models.TextField("รายละเอียด", blank=True)

    class Meta:
        ordering = ["base_price"]
        verbose_name = "ประเภทห้อง"
        verbose_name_plural = "ประเภทห้อง"

    def __str__(self):
        return self.name


class Room(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "available", "ว่าง"
        OCCUPIED = "occupied", "มีผู้เข้าพัก"
        CLEANING = "cleaning", "รอทำความสะอาด"
        MAINTENANCE = "maintenance", "ซ่อมบำรุง"

    number = models.CharField("หมายเลขห้อง", max_length=10, unique=True)
    room_type = models.ForeignKey(RoomType, on_delete=models.PROTECT, related_name="rooms", verbose_name="ประเภท")
    floor = models.PositiveSmallIntegerField("โซน/ชั้น", default=1)
    status = models.CharField("สถานะ", max_length=12, choices=Status.choices, default=Status.AVAILABLE)
    notes = models.CharField("หมายเหตุ", max_length=200, blank=True)

    class Meta:
        ordering = ["floor", "number"]
        verbose_name = "ห้องพัก"
        verbose_name_plural = "ห้องพัก"

    def __str__(self):
        return f"{self.number} · {self.room_type.name}"


class Booking(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "รอยืนยัน"
        CONFIRMED = "confirmed", "ยืนยันแล้ว"
        CHECKED_IN = "checked_in", "เช็คอินแล้ว"
        CHECKED_OUT = "checked_out", "เช็คเอาท์แล้ว"
        CANCELLED = "cancelled", "ยกเลิก"

    class Source(models.TextChoices):
        WALK_IN = "walk_in", "Walk-in"
        PHONE = "phone", "โทรศัพท์"
        LINE = "line", "LINE"
        WEBSITE = "website", "เว็บไซต์"
        OTA = "ota", "OTA (Agoda / Booking.com)"
        AGENT = "agent", "เอเจนซี่ทัวร์"

    ACTIVE_STATUSES = (Status.PENDING, Status.CONFIRMED, Status.CHECKED_IN)

    code = models.CharField("รหัสการจอง", max_length=20, unique=True, blank=True, editable=False)
    guest = models.ForeignKey(Guest, on_delete=models.PROTECT, related_name="bookings", verbose_name="ลูกค้า")
    room = models.ForeignKey(Room, on_delete=models.PROTECT, related_name="bookings", verbose_name="ห้อง")
    check_in = models.DateField("วันเช็คอิน")
    check_out = models.DateField("วันเช็คเอาท์")
    adults = models.PositiveSmallIntegerField("ผู้ใหญ่", default=2, validators=[MinValueValidator(1)])
    children = models.PositiveSmallIntegerField("เด็ก", default=0)
    status = models.CharField("สถานะ", max_length=12, choices=Status.choices, default=Status.PENDING)
    source = models.CharField("ช่องทางการจอง", max_length=10, choices=Source.choices, default=Source.WALK_IN)
    nightly_rate = models.DecimalField(
        "ราคาต่อคืน (บาท)", max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="เว้นว่างเพื่อใช้ราคาตั้งต้นของประเภทห้อง",
    )
    special_requests = models.TextField("คำขอพิเศษ", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+", verbose_name="บันทึกโดย",
    )

    class Meta:
        ordering = ["-check_in", "-id"]
        verbose_name = "การจอง"
        verbose_name_plural = "การจอง"
        indexes = [
            models.Index(fields=["room", "check_in", "check_out"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return self.code or f"Booking #{self.pk}"

    def get_absolute_url(self):
        return reverse("crm:booking_detail", args=[self.pk])

    # --- คำนวณยอด -------------------------------------------------------
    @property
    def nights(self) -> int:
        if not (self.check_in and self.check_out):
            return 0
        return max((self.check_out - self.check_in).days, 0)

    @property
    def total_amount(self) -> Decimal:
        return (self.nightly_rate or Decimal("0")) * self.nights

    @property
    def paid_amount(self) -> Decimal:
        return self.payments.aggregate(s=Sum("amount"))["s"] or Decimal("0")

    @property
    def balance(self) -> Decimal:
        return self.total_amount - self.paid_amount

    # --- Validation: กันจองซ้อน / เกินความจุ ---------------------------
    @classmethod
    def overlapping(cls, room_id, check_in, check_out, exclude_pk=None):
        qs = cls.objects.filter(
            room_id=room_id,
            status__in=cls.ACTIVE_STATUSES,
            check_in__lt=check_out,
            check_out__gt=check_in,
        )
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        return qs

    def clean(self):
        errors = {}
        if self.check_in and self.check_out and self.check_out <= self.check_in:
            errors["check_out"] = "วันเช็คเอาท์ต้องอยู่หลังวันเช็คอิน"
        if self.room_id and self.adults is not None:
            capacity = self.room.room_type.capacity
            if self.adults + (self.children or 0) > capacity:
                errors["adults"] = f"ห้องนี้รองรับได้สูงสุด {capacity} คน"
        if not errors and self.room_id and self.check_in and self.check_out and self.status in self.ACTIVE_STATUSES:
            clash = self.overlapping(self.room_id, self.check_in, self.check_out, exclude_pk=self.pk).first()
            if clash:
                errors["room"] = (
                    f"ห้องนี้ถูกจองแล้ว ({clash.code}: {clash.check_in:%d/%m} – {clash.check_out:%d/%m})"
                )
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.nightly_rate is None and self.room_id:
            self.nightly_rate = self.room.room_type.base_price
        super().save(*args, **kwargs)
        if not self.code:
            self.code = f"BK{self.created_at:%y%m}{self.pk:05d}"
            super().save(update_fields=["code"])


class Payment(models.Model):
    class Method(models.TextChoices):
        CASH = "cash", "เงินสด"
        TRANSFER = "transfer", "โอนเงิน"
        PROMPTPAY = "promptpay", "พร้อมเพย์"
        CARD = "card", "บัตรเครดิต/เดบิต"
        OTA = "ota", "ชำระผ่าน OTA"

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="payments", verbose_name="การจอง")
    amount = models.DecimalField("จำนวนเงิน (บาท)", max_digits=10, decimal_places=2,
                                 validators=[MinValueValidator(Decimal("0.01"))])
    method = models.CharField("วิธีชำระ", max_length=10, choices=Method.choices, default=Method.TRANSFER)
    reference = models.CharField("เลขอ้างอิง", max_length=100, blank=True)
    paid_at = models.DateTimeField("ชำระเมื่อ")
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+", verbose_name="รับเงินโดย",
    )

    class Meta:
        ordering = ["-paid_at"]
        verbose_name = "การชำระเงิน"
        verbose_name_plural = "การชำระเงิน"

    def __str__(self):
        return f"{self.booking} · ฿{self.amount:,.2f}"


class Interaction(models.Model):
    """บันทึกการติดต่อกับลูกค้า — หัวใจของ CRM"""

    class Channel(models.TextChoices):
        PHONE = "phone", "โทรศัพท์"
        LINE = "line", "LINE"
        EMAIL = "email", "อีเมล"
        FRONT_DESK = "front_desk", "หน้าเคาน์เตอร์"
        REVIEW = "review", "รีวิวออนไลน์"
        OTHER = "other", "อื่นๆ"

    guest = models.ForeignKey(Guest, on_delete=models.CASCADE, related_name="interactions", verbose_name="ลูกค้า")
    channel = models.CharField("ช่องทาง", max_length=12, choices=Channel.choices, default=Channel.PHONE)
    subject = models.CharField("เรื่อง", max_length=200)
    note = models.TextField("รายละเอียด", blank=True)
    follow_up_date = models.DateField("นัดติดตามวันที่", null=True, blank=True)
    done = models.BooleanField("ดำเนินการแล้ว", default=False)
    staff = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+", verbose_name="พนักงาน",
    )
    created_at = models.DateTimeField("บันทึกเมื่อ", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "การติดต่อลูกค้า"
        verbose_name_plural = "การติดต่อลูกค้า"

    def __str__(self):
        return f"{self.guest} · {self.subject}"
