import json
from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import connection, transaction
from django.db.models import Count, Max, Q, Sum
from django.db.models.functions import TruncDate
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from .forms import BookingForm, GuestForm, InteractionForm, PaymentForm
from .models import Booking, Guest, Interaction, Payment, Room

S = Booking.Status


def paginate(request, queryset, per_page=20):
    return Paginator(queryset, per_page).get_page(request.GET.get("page"))


# --- Health check (ใช้กับ Docker / Load balancer / Uptime monitor) ---------
@never_cache
def healthz(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:  # pragma: no cover
        return HttpResponse("database unavailable", status=503, content_type="text/plain")
    return HttpResponse("ok", content_type="text/plain")


# --- Dashboard ------------------------------------------------------------
@login_required
def dashboard(request):
    today = timezone.localdate()
    total_rooms = Room.objects.count()
    status_counts = {
        row["status"]: row["c"] for row in Room.objects.values("status").annotate(c=Count("id"))
    }
    in_house = Booking.objects.filter(status=S.CHECKED_IN).count()
    month_start = today.replace(day=1)

    context = {
        "today": today,
        "total_rooms": total_rooms,
        "in_house": in_house,
        "occupancy": round(in_house / total_rooms * 100) if total_rooms else 0,
        "room_status": [
            (value, label, status_counts.get(value, 0)) for value, label in Room.Status.choices
        ],
        "arrivals": Booking.objects.filter(check_in=today, status__in=[S.PENDING, S.CONFIRMED])
        .select_related("guest", "room"),
        "departures": Booking.objects.filter(check_out__lte=today, status=S.CHECKED_IN)
        .select_related("guest", "room"),
        "month_revenue": Payment.objects.filter(paid_at__date__gte=month_start)
        .aggregate(s=Sum("amount"))["s"] or Decimal("0"),
        "guest_count": Guest.objects.count(),
        "follow_ups": Interaction.objects.filter(
            done=False, follow_up_date__isnull=False, follow_up_date__lte=today + timedelta(days=7)
        ).select_related("guest").order_by("follow_up_date")[:8],
        "recent_bookings": Booking.objects.select_related("guest", "room").order_by("-created_at")[:6],
    }
    return render(request, "crm/dashboard.html", context)


# --- Guests ---------------------------------------------------------------
@login_required
def guest_list(request):
    qs = Guest.objects.annotate(
        stays=Count("bookings", filter=Q(bookings__status=S.CHECKED_OUT)),
        last_stay=Max("bookings__check_out", filter=Q(bookings__status=S.CHECKED_OUT)),
    ).order_by("-created_at")
    q = request.GET.get("q", "").strip()
    tier = request.GET.get("tier", "")
    if q:
        qs = qs.filter(
            Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(email__icontains=q)
            | Q(phone__icontains=q) | Q(line_id__icontains=q)
        )
    if tier in Guest.Tier.values:
        qs = qs.filter(tier=tier)
    return render(request, "crm/guest_list.html", {
        "page": paginate(request, qs), "q": q, "tier": tier, "tiers": Guest.Tier.choices,
    })


@login_required
def guest_detail(request, pk):
    guest = get_object_or_404(Guest, pk=pk)
    form = InteractionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        interaction = form.save(commit=False)
        interaction.guest = guest
        interaction.staff = request.user
        interaction.save()
        messages.success(request, "บันทึกการติดต่อแล้ว")
        return redirect(guest)

    bookings = guest.bookings.select_related("room__room_type")
    return render(request, "crm/guest_detail.html", {
        "guest": guest,
        "bookings": bookings,
        "interactions": guest.interactions.select_related("staff"),
        "form": form,
        "stays": bookings.filter(status=S.CHECKED_OUT).count(),
        "total_spent": Payment.objects.filter(booking__guest=guest).aggregate(s=Sum("amount"))["s"] or 0,
    })


@login_required
def guest_form(request, pk=None):
    guest = get_object_or_404(Guest, pk=pk) if pk else None
    form = GuestForm(request.POST or None, instance=guest)
    if request.method == "POST" and form.is_valid():
        guest = form.save()
        messages.success(request, f"บันทึกข้อมูลลูกค้า {guest.full_name} แล้ว")
        return redirect(guest)
    return render(request, "crm/form.html", {
        "form": form,
        "title": "แก้ไขข้อมูลลูกค้า" if pk else "เพิ่มลูกค้าใหม่",
        "back_url": guest.get_absolute_url() if guest else "/guests/",
    })


@login_required
@require_POST
def interaction_done(request, pk):
    interaction = get_object_or_404(Interaction, pk=pk)
    interaction.done = True
    interaction.save(update_fields=["done"])
    messages.success(request, "ปิดงานติดตามแล้ว")
    return redirect(request.POST.get("next") or interaction.guest.get_absolute_url())


# --- Rooms ----------------------------------------------------------------
@login_required
def room_board(request):
    rooms = Room.objects.select_related("room_type")
    current = {
        b.room_id: b for b in Booking.objects.filter(status=S.CHECKED_IN).select_related("guest")
    }
    floors = {}
    for room in rooms:
        room.current_booking = current.get(room.pk)
        floors.setdefault(room.floor, []).append(room)
    return render(request, "crm/room_board.html", {
        "floors": sorted(floors.items()), "statuses": Room.Status.choices,
    })


# --- Bookings -------------------------------------------------------------
@login_required
def booking_list(request):
    qs = Booking.objects.select_related("guest", "room__room_type")
    status = request.GET.get("status", "")
    q = request.GET.get("q", "").strip()
    if status in S.values:
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(
            Q(code__icontains=q) | Q(guest__first_name__icontains=q)
            | Q(guest__last_name__icontains=q) | Q(room__number__iexact=q)
        )
    counts = {row["status"]: row["c"] for row in Booking.objects.values("status").annotate(c=Count("id"))}
    return render(request, "crm/booking_list.html", {
        "page": paginate(request, qs), "q": q, "status": status,
        "tabs": [(v, l, counts.get(v, 0)) for v, l in S.choices],
        "total": sum(counts.values()),
    })


@login_required
def booking_detail(request, pk):
    booking = get_object_or_404(Booking.objects.select_related("guest", "room__room_type"), pk=pk)
    form = PaymentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        payment = form.save(commit=False)
        payment.booking = booking
        payment.paid_at = timezone.now()
        payment.received_by = request.user
        payment.save()
        messages.success(request, f"รับชำระ ฿{payment.amount:,.2f} แล้ว")
        return redirect(booking)
    return render(request, "crm/booking_detail.html", {
        "booking": booking,
        "payments": booking.payments.select_related("received_by"),
        "form": form,
        "today": timezone.localdate(),
    })


@login_required
def booking_form(request, pk=None):
    booking = get_object_or_404(Booking, pk=pk) if pk else None
    initial = {}
    if not booking:
        today = timezone.localdate()
        initial = {"check_in": today, "check_out": today + timedelta(days=1)}
        if request.GET.get("guest"):
            initial["guest"] = request.GET["guest"]
        if request.GET.get("room"):
            initial["room"] = request.GET["room"]
    form = BookingForm(request.POST or None, instance=booking, initial=initial)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        if not obj.pk:
            obj.created_by = request.user
        obj.save()
        messages.success(request, f"บันทึกการจอง {obj.code} แล้ว")
        return redirect(obj)
    return render(request, "crm/booking_form.html", {
        "form": form,
        "booking": booking,
        "title": f"แก้ไขการจอง {booking.code}" if booking else "สร้างการจองใหม่",
    })


TRANSITIONS = {
    "confirm": ({S.PENDING}, S.CONFIRMED, None, "ยืนยันการจองแล้ว"),
    "check_in": ({S.PENDING, S.CONFIRMED}, S.CHECKED_IN, Room.Status.OCCUPIED, "เช็คอินเรียบร้อย"),
    "check_out": ({S.CHECKED_IN}, S.CHECKED_OUT, Room.Status.CLEANING,
                  "เช็คเอาท์เรียบร้อย — ห้องถูกตั้งเป็น 'รอทำความสะอาด'"),
    "cancel": ({S.PENDING, S.CONFIRMED}, S.CANCELLED, None, "ยกเลิกการจองแล้ว"),
}


@login_required
@require_POST
def booking_action(request, pk, action):
    booking = get_object_or_404(Booking.objects.select_related("room"), pk=pk)
    if action not in TRANSITIONS:
        messages.error(request, "คำสั่งไม่ถูกต้อง")
        return redirect(booking)
    allowed_from, new_status, room_status, msg = TRANSITIONS[action]
    if booking.status not in allowed_from:
        messages.error(request, f"ไม่สามารถทำรายการได้ในสถานะ '{booking.get_status_display()}'")
        return redirect(booking)
    if action == "check_in" and booking.check_in > timezone.localdate():
        messages.error(request, "ยังไม่ถึงวันเช็คอิน")
        return redirect(booking)
    if action == "check_out" and booking.balance > 0:
        messages.warning(request, f"หมายเหตุ: ยังมียอดค้างชำระ ฿{booking.balance:,.2f}")

    with transaction.atomic():
        booking.status = new_status
        booking.save(update_fields=["status", "updated_at"])
        if room_status:
            booking.room.status = room_status
            booking.room.save(update_fields=["status"])
    messages.success(request, msg)
    return redirect(booking)


# --- JSON API (เรียกจาก static/js/app.js) ----------------------------------
@login_required
@require_GET
def api_revenue(request):
    try:
        days = min(max(int(request.GET.get("days", 14)), 1), 90)
    except ValueError:
        days = 14
    today = timezone.localdate()
    start = today - timedelta(days=days - 1)
    rows = (
        Payment.objects.filter(paid_at__date__gte=start)
        .annotate(d=TruncDate("paid_at"))
        .values("d")
        .annotate(total=Sum("amount"))
    )
    totals = {row["d"]: row["total"] for row in rows}
    data = []
    for i in range(days):
        d = start + timedelta(days=i)
        data.append({"date": d.isoformat(), "label": f"{d.day}/{d.month}", "total": float(totals.get(d, 0))})
    return JsonResponse({"days": data, "sum": sum(x["total"] for x in data)})


@login_required
@require_POST
def api_room_status(request, pk):
    room = get_object_or_404(Room, pk=pk)
    try:
        status = json.loads(request.body or "{}").get("status")
    except json.JSONDecodeError:
        status = None
    if status not in Room.Status.values:
        return JsonResponse({"error": "สถานะไม่ถูกต้อง"}, status=400)
    room.status = status
    room.save(update_fields=["status"])
    return JsonResponse({"id": room.pk, "status": room.status, "label": room.get_status_display()})


@login_required
@require_GET
def api_availability(request):
    check_in = parse_date(request.GET.get("check_in", ""))
    check_out = parse_date(request.GET.get("check_out", ""))
    if not check_in or not check_out or check_out <= check_in:
        return JsonResponse({"error": "ช่วงวันที่ไม่ถูกต้อง"}, status=400)
    busy = Booking.objects.filter(
        status__in=Booking.ACTIVE_STATUSES, check_in__lt=check_out, check_out__gt=check_in
    )
    exclude = request.GET.get("booking")
    if exclude and exclude.isdigit():
        busy = busy.exclude(pk=int(exclude))
    rooms = (
        Room.objects.exclude(pk__in=busy.values("room_id"))
        .exclude(status=Room.Status.MAINTENANCE)
        .select_related("room_type")
    )
    return JsonResponse({
        "nights": (check_out - check_in).days,
        "rooms": [
            {"id": r.pk, "number": r.number, "type": r.room_type.name,
             "capacity": r.room_type.capacity, "price": float(r.room_type.base_price)}
            for r in rooms
        ],
    })
