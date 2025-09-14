import threading
import time
import logging
import os
import tempfile
try:
    import fcntl  # POSIX file locking
except Exception:  # pragma: no cover
    fcntl = None
from django.utils import timezone
from django.db import close_old_connections
from django.conf import settings

from .models import CMLServer, HealthSettings
from .services import probe_health, check_and_release_expired_leases


_worker_thread = None
_lock_fd_global = None  # keep the lock FD open for the life of the process
logger = logging.getLogger(__name__)

# Track backoff per server to avoid spamming unreachable hosts
_fail_counts: dict[int, int] = {}
_skip_until: dict[int, float] = {}
_confirm_remaining: dict[int, int] = {}
_settings_snapshot: tuple | None = None

# Simple round-robin state to ensure we check one server per tick
_server_ids: list[int] = []
_server_idx: int = 0
_last_refresh: float = 0.0
_refresh_interval: float = 60.0  # seconds


def _loop():
    # Defaults; will be overridden by HealthSettings
    tick = getattr(settings, "HEALTH_SCHEDULER_TICK", 1)
    normal_interval = getattr(settings, "HEALTH_CHECK_INTERVAL", 30)
    while True:
        try:
            close_old_connections()
            # Load live health settings
            try:
                hs = HealthSettings.get_solo()
                tick = max(1, int(hs.scheduler_tick_sec))
                normal_interval = max(1, int(hs.check_interval_sec))
                quick_delay = max(1, int(hs.quick_retry_delay_sec))
                quick_retries = max(0, int(hs.quick_retries))
                backoff_base = max(1, int(hs.backoff_base_sec))
                backoff_max = max(backoff_base, int(hs.backoff_max_sec))
                global _settings_snapshot
                current = (tick, normal_interval, quick_delay, quick_retries, backoff_base, backoff_max, hs.mode)
                if _settings_snapshot != current:
                    _settings_snapshot = current
                    logger.info(
                        "Health settings applied: mode=%s, tick=%ss, interval=%ss, quick_retries=%s, quick_delay=%ss, backoff_base=%ss, backoff_max=%ss",
                        hs.mode, tick, normal_interval, quick_retries, quick_delay, backoff_base, backoff_max,
                    )
            except Exception:
                quick_delay = 5
                quick_retries = 3
                backoff_base = getattr(settings, "HEALTH_CHECK_BACKOFF_BASE", 15)
                backoff_max = getattr(settings, "HEALTH_CHECK_BACKOFF_MAX", 300)

            now = time.time()

            # Refresh the round-robin list periodically
            global _server_ids, _server_idx, _last_refresh
            if (now - _last_refresh) > _refresh_interval or not _server_ids:
                _server_ids = list(CMLServer.objects.order_by("pk").values_list("pk", flat=True))
                _server_idx = 0 if _server_idx >= max(1, len(_server_ids)) else _server_idx
                _last_refresh = now

            # Pick exactly one server per tick, respecting backoff
            picked = None
            total = len(_server_ids)
            attempts = 0
            while total and attempts < total:
                pk = _server_ids[_server_idx % total]
                _server_idx = (_server_idx + 1) % total
                until = _skip_until.get(pk, 0)
                if not until or now >= until:
                    picked = pk
                    break
                attempts += 1

            if picked is not None:
                try:
                    s = CMLServer.objects.get(pk=picked)
                except CMLServer.DoesNotExist:
                    pass
                else:
                    ok = probe_health(s)
                    now2 = time.time()
                    if ok:
                        _confirm_remaining.pop(s.pk, None)
                        _fail_counts.pop(s.pk, None)
                        _skip_until[s.pk] = now2 + normal_interval
                        s.last_health_ok = True
                        s.last_health_at = timezone.now()
                        if s.assigned_to:
                            if s.status != s.STATUS_IN_USE:
                                s.status = s.STATUS_IN_USE
                                s.save(update_fields=["last_health_ok", "last_health_at", "status"])
                            else:
                                s.save(update_fields=["last_health_ok", "last_health_at"])
                        else:
                            if s.status != s.STATUS_AVAILABLE:
                                s.status = s.STATUS_AVAILABLE
                                s.save(update_fields=["last_health_ok", "last_health_at", "status"])
                            else:
                                s.save(update_fields=["last_health_ok", "last_health_at"])
                    else:
                        if s.pk not in _confirm_remaining:
                            _confirm_remaining[s.pk] = quick_retries
                            _skip_until[s.pk] = now2 + quick_delay
                            logger.info(
                                "Health failure detected for %s; confirming with %d quick retries at %ds",
                                s.name, quick_retries, quick_delay,
                            )
                        else:
                            remaining = max(0, _confirm_remaining.get(s.pk, 0) - 1)
                            if remaining > 0:
                                _confirm_remaining[s.pk] = remaining
                                _skip_until[s.pk] = now2 + quick_delay
                                logger.info("Health confirmation retry for %s; %d attempt(s) remaining", s.name, remaining)
                            else:
                                _confirm_remaining.pop(s.pk, None)
                                if s.status != s.STATUS_UNAVAILABLE:
                                    s.mark_unavailable()
                                    logger.warning("Health marked UNAVAILABLE for %s after 4 failed checks", s.name)
                                n = _fail_counts.get(s.pk, 0) + 1
                                _fail_counts[s.pk] = n
                                delay = min(backoff_max, backoff_base * (2 ** (n - 1)))
                                _skip_until[s.pk] = now2 + delay

            check_and_release_expired_leases()
        except Exception:
            logger.exception("Background worker loop error")
        finally:
            time.sleep(tick)


def ensure_worker_running():
    global _worker_thread
    if _worker_thread and _worker_thread.is_alive():
        return

    lock_path = os.path.join(tempfile.gettempdir(), "cmlorc-health-worker.lock")
    lock_fd = None
    if fcntl is not None:
        try:
            lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            logger.info("Acquired health worker lock at %s", lock_path)
            # Keep FD open globally so the lock is held as long as this process lives
            global _lock_fd_global
            _lock_fd_global = lock_fd
        except Exception:
            try:
                if lock_fd is not None:
                    os.close(lock_fd)
            except Exception:
                pass
            return

    t = threading.Thread(target=_loop, name="cmlorc-worker", daemon=True)
    t.start()
    _worker_thread = t
