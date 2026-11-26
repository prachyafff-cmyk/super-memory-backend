from django.contrib import admin

from .models import Booking, Guest, Interaction, Payment, Room, RoomType


class InteractionInline(admin.TabularInline):
    model = Interaction
    extra = 0
    fields = ("channel", "subject", "follow_up_date", "done", "staff")


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0


@admin.register(Guest)
class GuestAdmin(admin.ModelAdmin):
    list_display = ("full_name", "phone", "email", "tier", "nationality", "created_at")
    list_filter = ("tier", "nationality", "marketing_opt_in")
    search_fields = ("first_name", "last_name", "phone", "email", "line_id")
    inlines = [InteractionInline]


@admin.register(RoomType)
class RoomTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "base_price", "capacity")


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("number", "room_type", "floor", "status")
    list_filter = ("status", "room_type", "floor")
    list_editable = ("status",)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("code", "guest", "room", "check_in", "check_out", "status", "source")
    list_filter = ("status", "source", "check_in")
    search_fields = ("code", "guest__first_name", "guest__last_name", "room__number")
    date_hierarchy = "check_in"
    autocomplete_fields = ("guest",)
    inlines = [PaymentInline]


@admin.register(Interaction)
class InteractionAdmin(admin.ModelAdmin):
    list_display = ("guest", "channel", "subject", "follow_up_date", "done", "created_at")
    list_filter = ("channel", "done")
