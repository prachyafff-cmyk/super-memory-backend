from django.urls import path

from . import views

app_name = "crm"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    # ลูกค้า
    path("guests/", views.guest_list, name="guest_list"),
    path("guests/new/", views.guest_form, name="guest_create"),
    path("guests/<int:pk>/", views.guest_detail, name="guest_detail"),
    path("guests/<int:pk>/edit/", views.guest_form, name="guest_update"),
    path("interactions/<int:pk>/done/", views.interaction_done, name="interaction_done"),
    # ห้องพัก
    path("rooms/", views.room_board, name="room_board"),
    # การจอง
    path("bookings/", views.booking_list, name="booking_list"),
    path("bookings/new/", views.booking_form, name="booking_create"),
    path("bookings/<int:pk>/", views.booking_detail, name="booking_detail"),
    path("bookings/<int:pk>/edit/", views.booking_form, name="booking_update"),
    path("bookings/<int:pk>/<str:action>/", views.booking_action, name="booking_action"),
    # JSON API
    path("api/revenue/", views.api_revenue, name="api_revenue"),
    path("api/availability/", views.api_availability, name="api_availability"),
    path("api/rooms/<int:pk>/status/", views.api_room_status, name="api_room_status"),
]
