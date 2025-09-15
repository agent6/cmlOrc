from __future__ import annotations

import logging
import threading
import urllib.error
from django.utils import timezone
from django.db import transaction
from typing import Iterable
from django.conf import settings

from .models import CMLServer, HealthSettings
from .cml import CMLClient

logger = logging.getLogger(__name__)


def _client(server: CMLServer, timeout: int | None = None) -> CMLClient:
    return CMLClient(
        base_url=server.base_url,
        username=server.username,
        password=server.password,
        verify_tls=server.verify_tls,
        timeout=timeout if timeout is not None else 10,
    )


def probe_health(server: CMLServer) -> bool:
    """Lightweight health probe.
    Strategy:
    1) If mode=ping, try unauthenticated ping first. If it fails, fall back to an authenticated list_labs() before declaring failure.
    2) If mode=labs, call list_labs() (authenticated) directly.
    Uses HealthSettings.http_timeout_sec for request timeout.
    """
    try:
        hs = HealthSettings.get_solo()
    except Exception:
        hs = None
    timeout = getattr(hs, "http_timeout_sec", 12)
    c = _client(server, timeout=timeout)

    try:
        mode = getattr(hs, "mode", HealthSettings.MODE_PING if hs else "ping")
        if mode == HealthSettings.MODE_PING:
            # First try unauthenticated reachability
            if c.ping():
                return True
            # Fallback: try an authenticated lightweight call before failing
            try:
                c.list_labs()
                return True
            except Exception as e:
                logger.debug("Health probe (fallback list) failed for %s: %s", server.name, e)
                return False
        else:
            c.list_labs()
            return True
    except urllib.error.URLError as e:
        logger.debug("Health probe network error for %s (%s): %s", server.name, server.base_url, e)
        return False
    except Exception as e:
        logger.debug("Health probe failed for %s (%s): %s", server.name, server.base_url, e)
        return False


def ensure_only_lab_running_and_wiped_then_start(server: CMLServer, lab_uuid: str):
    c = _client(server)
    c.authenticate()
    labs = c.list_labs()
    if isinstance(labs, dict):
        lab_uuids = list(labs.keys())
    elif isinstance(labs, list):
        lab_uuids = labs
    else:
        lab_uuids = []

    target_running = False
    try:
        info = c.lab_info(lab_uuid)
        if isinstance(info, dict):
            state = info.get("state")
            if isinstance(state, dict):
                target_running = state.get("status") == "STARTED"
            elif isinstance(state, str):
                target_running = state.upper() in {"STARTED", "RUNNING"}
    except Exception:
        target_running = False

    if not target_running:
        for l in lab_uuids:
            try:
                c.stop_lab(l)
            except Exception:
                logger.exception("Failed to stop lab %s on %s", l, server.name)
        for l in lab_uuids:
            try:
                ok = c.wait_for_lab_not_running(l, timeout=180)
                if not ok:
                    logger.warning("Lab %s did not stop within timeout on %s", l, server.name)
            except Exception:
                logger.exception("Error waiting for lab %s to stop on %s", l, server.name)
        for l in lab_uuids:
            try:
                c.wipe_lab(l)
            except Exception:
                logger.exception("Failed to wipe lab %s on %s", l, server.name)
        try:
            c.start_lab(lab_uuid)
        except Exception:
            logger.exception("Failed to start target lab %s on %s", lab_uuid, server.name)
            raise


def assign_server_to_student_by_name(server: CMLServer, user, lab_name_or_uuid: str, minutes: int = 240):
    """Assign user to a lab on this server.
    If the same user re-assigns to the same lab currently on this server,
    only extend the lease time and avoid stopping/wiping/restarting labs.
    """
    c = _client(server)
    c.authenticate()
    lab_uuid = c.resolve_lab_uuid_by_name(lab_name_or_uuid)
    if not lab_uuid:
        raise ValueError(f"Lab not found by name or UUID: {lab_name_or_uuid}")

    # If same user + same lab, extend lease only
    same_user = server.assigned_to_id == getattr(user, "id", None)
    same_lab = False
    try:
        if server.assigned_lab_uuid and server.assigned_lab_uuid == lab_uuid:
            same_lab = True
        elif server.assigned_lab_name and lab_name_or_uuid and server.assigned_lab_name.strip().lower() == lab_name_or_uuid.strip().lower():
            same_lab = True
    except Exception:
        same_lab = False

    if same_user and same_lab:
        with transaction.atomic():
            now = timezone.now()
            server.assigned_until = now + timezone.timedelta(minutes=minutes)
            server.save(update_fields=["assigned_until"])
        return

    # Otherwise, perform full assignment and lab preparation
    with transaction.atomic():
        server.assign(user, lab_uuid, minutes=minutes, lab_name=lab_name_or_uuid)
    ensure_only_lab_running_and_wiped_then_start(server, lab_uuid)


def get_user_assignment(user) -> CMLServer | None:
    try:
        return CMLServer.objects.get(assigned_to=user)
    except CMLServer.DoesNotExist:
        return None


def find_first_available_server() -> CMLServer | None:
    qs = (
        CMLServer.objects.filter(assigned_to__isnull=True, status=CMLServer.STATUS_AVAILABLE, last_health_ok=True)
        .order_by("name")
    )
    return qs.first()


def assign_via_pool(user, lab_name_or_uuid: str, minutes: int = 240) -> CMLServer:
    current = get_user_assignment(user)
    target_server = current or find_first_available_server()
    if not target_server:
        raise ValueError("No servers available")
    assign_server_to_student_by_name(target_server, user, lab_name_or_uuid, minutes=minutes)
    return target_server


def _release_cleanup(server_pk: int):
    try:
        s = CMLServer.objects.get(pk=server_pk)
    except CMLServer.DoesNotExist:
        return
    try:
        if s.assigned_to:
            return
        c = _client(s, timeout=getattr(settings, "HEALTH_CHECK_HTTP_TIMEOUT", 12))
        try:
            if not CMLClient(c.base_url, c.username, c.password, c.verify_tls, c.timeout).ping():
                return
        except Exception:
            pass
        try:
            c.authenticate()
        except Exception:
            return
        try:
            labs = c.list_labs()
        except Exception:
            return
        if isinstance(labs, dict):
            lab_uuids = list(labs.keys())
        elif isinstance(labs, list):
            lab_uuids = labs
        else:
            lab_uuids = []
        for l in lab_uuids:
            try:
                if CMLServer.objects.filter(pk=server_pk, assigned_to__isnull=False).exists():
                    break
                c.stop_lab(l)
            except Exception:
                logger.debug("Release cleanup: stop failed for %s on %s", l, s.name)
        for l in lab_uuids:
            try:
                if CMLServer.objects.filter(pk=server_pk, assigned_to__isnull=False).exists():
                    break
                c.wait_for_lab_not_running(l, timeout=120)
            except Exception:
                pass
        for l in lab_uuids:
            try:
                if CMLServer.objects.filter(pk=server_pk, assigned_to__isnull=False).exists():
                    break
                c.wipe_lab(l)
            except Exception:
                logger.debug("Release cleanup: wipe failed for %s on %s", l, s.name)
    except Exception:
        logger.debug("Release cleanup: unexpected error", exc_info=True)


def release_server(server: CMLServer, stop_and_wipe: bool = True):
    server.release()
    if not stop_and_wipe:
        return
    try:
        t = threading.Thread(target=_release_cleanup, args=(server.pk,), name=f"release-cleanup-{server.pk}", daemon=True)
        t.start()
    except Exception:
        logger.debug("Failed to start release cleanup thread", exc_info=True)


def check_and_release_expired_leases():
    now = timezone.now()
    expired_qs = CMLServer.objects.filter(assigned_until__isnull=False, assigned_until__lt=now)
    count = expired_qs.count()
    if count:
        logger.info("Lease sweeper: releasing %d expired assignment(s)", count)
    for s in expired_qs:
        try:
            release_server(s)
        except Exception:
            logger.exception("Lease sweeper: error releasing %s", s.name)


def record_pool_snapshot():
    try:
        from .models import PoolStat
        total = CMLServer.objects.count()
        available = CMLServer.objects.filter(status=CMLServer.STATUS_AVAILABLE).count()
        in_use = CMLServer.objects.filter(status=CMLServer.STATUS_IN_USE).count()
        unavailable = CMLServer.objects.filter(status=CMLServer.STATUS_UNAVAILABLE).count()
        initializing = CMLServer.objects.filter(status=CMLServer.STATUS_INITIALIZING).count()
        PoolStat.objects.create(
            total=total,
            available=available,
            in_use=in_use,
            unavailable=unavailable,
            initializing=initializing,
        )
    except Exception as e:
        # If table doesn't exist yet, try to create it dynamically (dev convenience)
        try:
            from django.db import connection
            from .models import PoolStat
            with connection.schema_editor() as se:
                se.create_model(PoolStat)
        except Exception:
            # Ignore if creation fails; user can run migrations instead
            pass


def push_lab_yaml_to_server(server: CMLServer, yaml_text: str):
    try:
        c = _client(server, timeout=getattr(settings, "IMPORT_HTTP_TIMEOUT", 8))
        title = CMLClient.extract_lab_title_from_yaml(yaml_text)
        removed = 0
        # Pre-import duplicate cleanup if we know the title
        if title:
            try:
                labs = c.list_labs()
                if isinstance(labs, dict):
                    items = list(labs.items())  # (uuid, name)
                    matches = [u for u, nm in items if isinstance(nm, str) and nm.strip().lower() == title.lower()]
                elif isinstance(labs, list):
                    # need to fetch names
                    matches = []
                    for u in labs:
                        try:
                            info = c.lab_info(u)
                            nm = None
                            if isinstance(info, dict):
                                nm = (
                                    info.get("title")
                                    or info.get("lab_title")
                                    or info.get("label")
                                    or info.get("name")
                                )
                            if isinstance(nm, str) and nm.strip().lower() == title.lower():
                                matches.append(u)
                        except Exception:
                            continue
                else:
                    matches = []
                for u in matches:
                    try:
                        c.stop_lab(u)
                    except Exception:
                        pass
                    try:
                        c.wait_for_lab_not_running(u, timeout=120)
                    except Exception:
                        pass
                    try:
                        c.wipe_lab(u)
                    except Exception:
                        pass
                    try:
                        c.delete_lab(u)
                        removed += 1
                    except Exception:
                        # continue even if delete fails
                        pass
            except Exception:
                # If listing fails, continue to import anyway
                pass

        resp = c.import_lab_yaml(yaml_text)
        return {"ok": True, "response": resp, "title": title, "removed": removed}
    except Exception as e:
        title = None
        try:
            title = CMLClient.extract_lab_title_from_yaml(yaml_text)
        except Exception:
            pass
        return {"ok": False, "error": str(e), "title": title, "removed": 0}
