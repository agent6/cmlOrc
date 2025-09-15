from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from typing import Optional
from django.db import connection


User = get_user_model()


class CMLServer(models.Model):
    name = models.CharField(max_length=100, unique=True)
    base_url = models.URLField(help_text="Base API URL, e.g. https://host/api/v0")
    username = models.CharField(max_length=150)
    password = models.CharField(max_length=255)
    verify_tls = models.BooleanField(default=False, help_text="Verify TLS certificates (False for self-signed in dev)")

    STATUS_AVAILABLE = "available"
    STATUS_IN_USE = "in_use"
    STATUS_UNAVAILABLE = "unavailable"
    STATUS_INITIALIZING = "initializing"
    STATUS_CHOICES = [
        (STATUS_AVAILABLE, "Available"),
        (STATUS_IN_USE, "In Use"),
        (STATUS_UNAVAILABLE, "Unavailable"),
        (STATUS_INITIALIZING, "Initializing"),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_INITIALIZING)
    last_health_ok = models.BooleanField(default=False)
    last_health_at = models.DateTimeField(null=True, blank=True)

    assigned_to = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_cml_servers")
    assigned_lab_uuid = models.CharField(max_length=64, null=True, blank=True)
    assigned_lab_name = models.CharField(max_length=255, null=True, blank=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    assigned_until = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.base_url})"

    def mark_unavailable(self):
        self.last_health_ok = False
        self.status = self.STATUS_UNAVAILABLE
        self.last_health_at = timezone.now()
        self.save(update_fields=["last_health_ok", "status", "last_health_at"])

    def mark_available(self):
        self.last_health_ok = True
        if not self.assigned_to:
            self.status = self.STATUS_AVAILABLE
        self.last_health_at = timezone.now()
        self.save(update_fields=["last_health_ok", "status", "last_health_at"])

    def assign(self, user, lab_uuid: str, minutes: int = 240, lab_name: Optional[str] = None):
        now = timezone.now()
        self.assigned_to = user
        self.assigned_lab_uuid = lab_uuid
        self.assigned_lab_name = lab_name
        self.assigned_at = now
        self.assigned_until = now + timezone.timedelta(minutes=minutes)
        self.status = self.STATUS_IN_USE
        self.save()

    def release(self):
        self.assigned_to = None
        self.assigned_lab_uuid = None
        self.assigned_lab_name = None
        self.assigned_at = None
        self.assigned_until = None
        self.status = self.STATUS_AVAILABLE if self.last_health_ok else self.STATUS_UNAVAILABLE
        self.save()


class HealthSettings(models.Model):
    MODE_PING = "ping"
    MODE_LABS = "labs"
    MODE_CHOICES = [
        (MODE_PING, "Lightweight (HEAD/GET ping)"),
        (MODE_LABS, "Full (authenticate + list labs)"),
    ]

    mode = models.CharField(max_length=10, choices=MODE_CHOICES, default=MODE_PING)
    check_interval_sec = models.PositiveIntegerField(default=30)
    scheduler_tick_sec = models.PositiveIntegerField(default=1)
    http_timeout_sec = models.PositiveIntegerField(default=12)
    quick_retries = models.PositiveIntegerField(default=3)
    quick_retry_delay_sec = models.PositiveIntegerField(default=5)
    backoff_base_sec = models.PositiveIntegerField(default=15)
    backoff_max_sec = models.PositiveIntegerField(default=300)
    stats_interval_sec = models.PositiveIntegerField(default=60)

    @classmethod
    def get_solo(cls) -> "HealthSettings":
        try:
            obj = cls.objects.first()
        except Exception:
            # Attempt to add missing stats_interval_sec dynamically (dev convenience)
            try:
                with connection.schema_editor() as se:
                    field = models.PositiveIntegerField(default=60)
                    field.set_attributes_from_name("stats_interval_sec")
                    se.add_field(cls, field)
            except Exception:
                pass
            obj = cls.objects.first()
        if obj:
            return obj
        return cls.objects.create()

    def __str__(self):
        return "Health Settings"


class PoolStat(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    total = models.PositiveIntegerField()
    available = models.PositiveIntegerField()
    in_use = models.PositiveIntegerField()
    unavailable = models.PositiveIntegerField()
    initializing = models.PositiveIntegerField()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"PoolStat {self.created_at:%Y-%m-%d %H:%M:%S} avail={self.available}/{self.total}"
