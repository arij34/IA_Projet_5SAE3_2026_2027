from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "role", "moderation_status", "is_staff")
    list_filter = UserAdmin.list_filter + ("role", "moderation_status")
    search_fields = ("username", "email", "title")

    fieldsets = UserAdmin.fieldsets + (
        ("Rôle et profil", {"fields": ("role", "title", "bio", "skills", "hourly_rate")}),
        ("Modération", {"fields": ("moderation_status", "moderation_checked_at")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Informations complémentaires", {"fields": ("email", "role")}),
    )