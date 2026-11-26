from django import forms

from .models import Booking, Guest, Interaction, Payment, Room

DATE = {"type": "date"}


class StyledFormMixin:
    """ใส่ class ของ Tailwind ให้ทุก widget อัตโนมัติ"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "checkbox")
            else:
                widget.attrs.setdefault("class", "input")
            if isinstance(widget, forms.Textarea):
                widget.attrs.setdefault("rows", 3)


class GuestForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Guest
        fields = [
            "first_name", "last_name", "phone", "email", "line_id",
            "nationality", "tier", "birthday", "marketing_opt_in", "notes",
        ]
        widgets = {"birthday": forms.DateInput(attrs=DATE, format="%Y-%m-%d")}


class RoomChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.number} · {obj.room_type.name} (฿{obj.room_type.base_price:,.0f}/คืน, {obj.room_type.capacity} คน)"


class BookingForm(StyledFormMixin, forms.ModelForm):
    room = RoomChoiceField(queryset=Room.objects.select_related("room_type"), label="ห้อง")

    class Meta:
        model = Booking
        fields = [
            "guest", "check_in", "check_out", "room", "adults", "children",
            "source", "status", "nightly_rate", "special_requests",
        ]
        widgets = {
            "check_in": forms.DateInput(attrs=DATE, format="%Y-%m-%d"),
            "check_out": forms.DateInput(attrs=DATE, format="%Y-%m-%d"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["guest"].queryset = Guest.objects.order_by("first_name", "last_name")
        # JS ใช้ attribute นี้เรียก API ตรวจห้องว่าง
        self.fields["room"].widget.attrs["data-availability"] = "1"


class PaymentForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Payment
        fields = ["amount", "method", "reference"]


class InteractionForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Interaction
        fields = ["channel", "subject", "note", "follow_up_date"]
        widgets = {"follow_up_date": forms.DateInput(attrs=DATE, format="%Y-%m-%d")}
