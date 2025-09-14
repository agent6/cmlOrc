from django.contrib import admin
from .models import CMLServer, HealthSettings


@admin.register(CMLServer)
class CMLServerAdmin(admin.ModelAdmin):
    list_display = ("name", "base_url", "status", "assigned_to", "assigned_lab_uuid", "last_health_ok", "last_health_at")
    list_filter = ("status", "last_health_ok", "verify_tls")
    search_fields = ("name", "base_url", "assigned_lab_uuid", "assigned_to__username")
    readonly_fields = ("status", "last_health_ok", "last_health_at", "assigned_at", "assigned_until")


@admin.register(HealthSettings)
class HealthSettingsAdmin(admin.ModelAdmin):
    list_display = ("mode", "check_interval_sec", "scheduler_tick_sec", "http_timeout_sec", "quick_retries")

