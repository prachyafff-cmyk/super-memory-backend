from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()

# คลาสสีของ badge (อยู่ในไฟล์ .py — tailwind.config.js สแกนไฟล์นี้ด้วย)
BADGE_CLASSES = {
    "pending": "bg-amber-100 text-amber-800",
    "confirmed": "bg-sky-100 text-sky-800",
    "checked_in": "bg-emerald-100 text-emerald-800",
    "checked_out": "bg-slate-200 text-slate-700",
    "cancelled": "bg-rose-100 text-rose-700",
    "available": "bg-emerald-100 text-emerald-800",
    "occupied": "bg-sky-100 text-sky-800",
    "cleaning": "bg-amber-100 text-amber-800",
    "maintenance": "bg-rose-100 text-rose-700",
    "vip": "bg-purple-100 text-purple-800",
    "gold": "bg-yellow-100 text-yellow-800",
    "silver": "bg-slate-200 text-slate-700",
    "regular": "bg-slate-100 text-slate-600",
}


@register.filter
def badge(value):
    return BADGE_CLASSES.get(value, "bg-slate-100 text-slate-600")


@register.filter
def baht(value, decimals=0):
    try:
        number = Decimal(value or 0)
    except (InvalidOperation, TypeError, ValueError):
        return value
    return f"฿{number:,.{int(decimals)}f}"
