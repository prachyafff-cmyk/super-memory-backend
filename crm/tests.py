import json
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Booking, Guest, Room, RoomType


class BaseCase(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("staff", password="pass12345!")
        self.rt = RoomType.objects.create(name="Pool Villa", base_price=Decimal("4500"), capacity=3)
        self.room = Room.objects.create(number="P01", room_type=self.rt)
        self.guest = Guest.objects.create(first_name="สมชาย", last_name="ใจดี")
        self.today = timezone.localdate()

    def book(self, offset=0, nights=2, **kw):
        ci = self.today + timedelta(days=offset)
        b = Booking(guest=self.guest, room=self.room, check_in=ci, check_out=ci + timedelta(days=nights), **kw)
        b.full_clean()
        b.save()
        return b


class BookingModelTests(BaseCase):
    def test_code_rate_and_total(self):
        b = self.book(nights=3)
        self.assertTrue(b.code.startswith("BK"))
        self.assertEqual(b.nightly_rate, Decimal("4500"))
        self.assertEqual(b.total_amount, Decimal("13500"))

    def test_overlap_rejected(self):
        self.book(offset=0, nights=3)
        with self.assertRaises(ValidationError) as ctx:
            self.book(offset=2, nights=2)
        self.assertIn("room", ctx.exception.message_dict)

    def test_back_to_back_allowed(self):
        self.book(offset=0, nights=2)
        self.book(offset=2, nights=2)  # เช็คเอาท์วันเดียวกับที่อีกคนเช็คอิน = ได้

    def test_cancelled_does_not_block(self):
        b = self.book(offset=0, nights=2)
        b.status = Booking.Status.CANCELLED
        b.save()
        self.book(offset=0, nights=2)

    def test_capacity(self):
        with self.assertRaises(ValidationError):
            self.book(adults=3, children=1)


class ViewTests(BaseCase):
    def setUp(self):
        super().setUp()
        self.client.login(username="staff", password="pass12345!")

    def test_login_required(self):
        self.client.logout()
        res = self.client.get(reverse("crm:dashboard"))
        self.assertEqual(res.status_code, 302)

    def test_healthz(self):
        self.client.logout()
        self.assertEqual(self.client.get("/healthz/").content, b"ok")

    def test_pages_render(self):
        b = self.book()
        for url in [
            reverse("crm:dashboard"), reverse("crm:guest_list"), reverse("crm:room_board"),
            reverse("crm:booking_list"), reverse("crm:booking_create"), reverse("crm:guest_create"),
            reverse("crm:guest_detail", args=[self.guest.pk]), reverse("crm:booking_detail", args=[b.pk]),
            reverse("crm:booking_update", args=[b.pk]), reverse("crm:api_revenue"),
        ]:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_check_in_and_out_flow(self):
        b = self.book()
        self.client.post(reverse("crm:booking_action", args=[b.pk, "check_in"]))
        b.refresh_from_db(); self.room.refresh_from_db()
        self.assertEqual(b.status, Booking.Status.CHECKED_IN)
        self.assertEqual(self.room.status, Room.Status.OCCUPIED)
        self.client.post(reverse("crm:booking_action", args=[b.pk, "check_out"]))
        b.refresh_from_db(); self.room.refresh_from_db()
        self.assertEqual(b.status, Booking.Status.CHECKED_OUT)
        self.assertEqual(self.room.status, Room.Status.CLEANING)

    def test_availability_api(self):
        self.book(offset=0, nights=2)
        url = reverse("crm:api_availability")
        busy = self.client.get(url, {"check_in": self.today, "check_out": self.today + timedelta(days=1)}).json()
        free = self.client.get(url, {"check_in": self.today + timedelta(days=2),
                                     "check_out": self.today + timedelta(days=3)}).json()
        self.assertEqual(busy["rooms"], [])
        self.assertEqual(len(free["rooms"]), 1)

    def test_room_status_api(self):
        url = reverse("crm:api_room_status", args=[self.room.pk])
        res = self.client.post(url, json.dumps({"status": "cleaning"}), content_type="application/json")
        self.assertEqual(res.status_code, 200)
        bad = self.client.post(url, json.dumps({"status": "nope"}), content_type="application/json")
        self.assertEqual(bad.status_code, 400)

    def test_create_booking_via_form(self):
        res = self.client.post(reverse("crm:booking_create"), {
            "guest": self.guest.pk, "room": self.room.pk, "check_in": self.today,
            "check_out": self.today + timedelta(days=1), "adults": 2, "children": 0,
            "source": "phone", "status": "pending",
        })
        self.assertEqual(res.status_code, 302)
        self.assertEqual(Booking.objects.get().created_by, self.user)


class SeedTests(TestCase):
    def test_seed_demo(self):
        call_command("seed_demo", verbosity=0)
        self.assertGreater(Booking.objects.count(), 20)
        # ข้อมูลตัวอย่างต้องไม่มีการจองซ้อน
        for b in Booking.objects.filter(status__in=Booking.ACTIVE_STATUSES):
            self.assertFalse(Booking.overlapping(b.room_id, b.check_in, b.check_out, b.pk).exists())
