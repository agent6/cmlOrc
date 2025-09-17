from django.contrib import admin
from .models import CMLServer, HealthSettings, PoolStat, LeaseLog


@admin.register(CMLServer)
class CMLServerAdmin(admin.ModelAdmin):
    list_display = ("name", "base_url", "status", "assigned_to", "assigned_lab_uuid", "last_health_ok", "last_health_at")
    list_filter = ("status", "last_health_ok", "verify_tls")
    search_fields = ("name", "base_url", "assigned_lab_uuid", "assigned_to__username")
    readonly_fields = ("status", "last_health_ok", "last_health_at", "assigned_at", "assigned_until")


@admin.register(HealthSettings)
class HealthSettingsAdmin(admin.ModelAdmin):
    list_display = ("mode", "check_interval_sec", "scheduler_tick_sec", "http_timeout_sec", "quick_retries")


@admin.register(PoolStat)
class PoolStatAdmin(admin.ModelAdmin):
    list_display = ("created_at", "total", "available", "in_use", "unavailable", "initializing")
    ordering = ("-created_at",)


@admin.register(LeaseLog)
class LeaseLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "event", "username", "server_name", "lab_name", "lab_uuid", "minutes")
    list_filter = ("event",)
    search_fields = ("username", "server_name", "lab_name", "lab_uuid")
    ordering = ("-created_at",)
