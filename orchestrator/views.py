from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
import json
import socket
from urllib.parse import urlsplit
import ipaddress
from django.http import JsonResponse, HttpResponse
import json
import socket
from urllib.parse import urlsplit
import ipaddress
import uuid

from .models import CMLServer, HealthSettings, LeaseLog
from django.db import connection
from django.db.models import Q
from .forms import (
    CMLServerForm,
    AssignmentForm,
    LabUploadForm,
    HealthSettingsForm,
    UserCreateForm,
    UserEditForm,
    UserPasswordForm,
)
from .services import (
    assign_server_to_student_by_name,
    assign_via_pool,
    release_server,
    check_and_release_expired_leases,
    push_lab_yaml_to_server,
    probe_health,
)
from .cml import CMLClient


@login_required
def home(request):
    servers = CMLServer.objects.all().order_by("name")
    total = servers.count()
    available = servers.filter(status=CMLServer.STATUS_AVAILABLE).count()
    return render(request, "orchestrator/home.html", {"servers": servers, "pool_total": total, "pool_available": available})


@login_required
def server_add(request):
    if request.method == "POST":
        form = CMLServerForm(request.POST)
        if form.is_valid():
            server = form.save()
            # Do an immediate health probe to avoid waiting for the worker
            try:
                from .services import probe_health
                ok = probe_health(server)
                from django.utils import timezone
                server.last_health_at = timezone.now()
                server.last_health_ok = bool(ok)
                if ok and not server.assigned_to:
                    server.status = server.STATUS_AVAILABLE
                elif not ok:
                    server.status = server.STATUS_UNAVAILABLE
                server.save(update_fields=["last_health_ok", "last_health_at", "status"])
            except Exception:
                pass
            messages.success(request, "Server added and probed.")
            return redirect("orchestrator:home")
    else:
        form = CMLServerForm()
    return render(request, "orchestrator/server_form.html", {"form": form, "title": "Add CML Server"})


@login_required
def pool_assign(request):
    if request.method == "POST":
        form = AssignmentForm(request.POST)
        if form.is_valid():
            user = form.cleaned_data["user"]
            lab_name = form.cleaned_data["lab_name"]
            minutes = form.cleaned_data["minutes"]
            try:
                server = assign_via_pool(user, lab_name, minutes=minutes)
                messages.success(request, f"Assigned {server.name} to {user.username} for {minutes}m and prepared lab '{lab_name}'.")
                return redirect("orchestrator:home")
            except Exception as e:
                messages.error(request, f"Assignment failed: {e}")
    else:
        form = AssignmentForm()
    return render(request, "orchestrator/pool_assign.html", {"form": form})


@login_required
def server_edit(request, pk: int):
    server = get_object_or_404(CMLServer, pk=pk)
    if request.method == "POST":
        form = CMLServerForm(request.POST, instance=server)
        if form.is_valid():
            form.save()
            messages.success(request, "Server updated.")
            return redirect("orchestrator:home")
    else:
        form = CMLServerForm(instance=server)
    return render(request, "orchestrator/server_form.html", {"form": form, "title": f"Edit {server.name}"})


@login_required
def server_clone(request, pk: int):
    src = get_object_or_404(CMLServer, pk=pk)
    if request.method == "POST":
        form = CMLServerForm(request.POST)
        if form.is_valid():
            server = form.save()
            try:
                from .services import probe_health
                ok = probe_health(server)
                from django.utils import timezone
                server.last_health_at = timezone.now()
                server.last_health_ok = bool(ok)
                if ok and not server.assigned_to:
                    server.status = server.STATUS_AVAILABLE
                elif not ok:
                    server.status = server.STATUS_UNAVAILABLE
                server.save(update_fields=["last_health_ok", "last_health_at", "status"])
            except Exception:
                pass
            messages.success(request, f"Cloned from {src.name} and probed.")
            return redirect("orchestrator:home")
    else:
        initial = {
            "base_url": src.base_url,
            "username": src.username,
            "password": src.password,
            "verify_tls": src.verify_tls,
        }
        form = CMLServerForm(initial=initial)
    return render(request, "orchestrator/server_form.html", {"form": form, "title": f"Clone from {src.name}"})


@login_required
def server_test(request, pk: int):
    server = get_object_or_404(CMLServer, pk=pk)
    try:
        c = CMLClient(server.base_url, server.username, server.password, verify_tls=server.verify_tls)
        token = c.authenticate()
        labs = c.list_labs()
        # Also perform a health probe and update status/health
        ok = probe_health(server)
        if ok:
            from django.utils import timezone
            server.last_health_ok = True
            server.last_health_at = timezone.now()
            if server.assigned_to:
                server.status = server.STATUS_IN_USE
            else:
                server.status = server.STATUS_AVAILABLE
            server.save(update_fields=["last_health_ok", "last_health_at", "status"])
            messages.success(request, f"Connection OK and health OK. Labs response type: {type(labs).__name__}.")
        else:
            server.mark_unavailable()
            messages.warning(request, "Connection OK but health probe failed; marked Unavailable.")
    except Exception as e:
        # Mark unavailable on test failure
        try:
            server.mark_unavailable()
        except Exception:
            pass
        messages.error(request, f"Connection failed: {e}")
    return redirect("orchestrator:home")


@login_required
def server_assign(request, pk: int):
    server = get_object_or_404(CMLServer, pk=pk)
    if request.method == "POST":
        form = AssignmentForm(request.POST)
        if form.is_valid():
            user = form.cleaned_data["user"]
            lab_name = form.cleaned_data["lab_name"]
            minutes = form.cleaned_data["minutes"]
            try:
                assign_server_to_student_by_name(server, user, lab_name, minutes=minutes)
                messages.success(request, f"Assigned {server.name} to {user.username} for {minutes}m and prepared lab '{lab_name}'.")
                return redirect("orchestrator:home")
            except Exception as e:
                messages.error(request, f"Assignment failed: {e}")
    else:
        initial = {}
        if server.assigned_to:
            initial.update({"user": server.assigned_to, "lab_name": server.assigned_lab_name or server.assigned_lab_uuid or ""})
        form = AssignmentForm(initial=initial)
    return render(request, "orchestrator/assign_form.html", {"form": form, "server": server})


@login_required
def server_release(request, pk: int):
    server = get_object_or_404(CMLServer, pk=pk)
    if request.method == "POST":
        release_server(server)
        messages.success(request, f"Released {server.name} and scheduled cleanup.")
        return redirect("orchestrator:home")
    return render(request, "orchestrator/release_confirm.html", {"server": server})


@login_required
def server_delete(request, pk: int):
    server = get_object_or_404(CMLServer, pk=pk)
    if request.method == "POST":
        name = server.name
        server.delete()
        messages.success(request, f"Deleted server {name}.")
        return redirect("orchestrator:home")
    return render(request, "orchestrator/server_delete_confirm.html", {"server": server})


# -----------------------------
# User management (staff-only)
# -----------------------------

def _staff_required(user):
    return user.is_authenticated and user.is_staff


@login_required
@user_passes_test(_staff_required)
def user_list(request):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    users = User.objects.order_by("username")
    return render(request, "orchestrator/users_list.html", {"users": users})


@login_required
@user_passes_test(_staff_required)
def user_add(request):
    if request.method == "POST":
        form = UserCreateForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "User created.")
            return redirect("orchestrator:user_list")
    else:
        form = UserCreateForm()
    return render(request, "orchestrator/user_form.html", {"form": form, "title": "Add User"})


@login_required
@user_passes_test(_staff_required)
def user_edit(request, pk: int):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    u = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        form = UserEditForm(request.POST, instance=u)
        if form.is_valid():
            form.save()
            messages.success(request, "User updated.")
            return redirect("orchestrator:user_list")
    else:
        form = UserEditForm(instance=u, initial={"is_staff": u.is_staff})
    return render(request, "orchestrator/user_form.html", {"form": form, "title": f"Edit {u.username}"})


@login_required
@user_passes_test(_staff_required)
def user_password(request, pk: int):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    u = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        form = UserPasswordForm(request.POST)
        if form.is_valid():
            u.set_password(form.cleaned_data["password1"])
            u.save(update_fields=["password"])
            messages.success(request, "Password updated.")
            return redirect("orchestrator:user_list")
    else:
        form = UserPasswordForm()
    return render(request, "orchestrator/user_password_form.html", {"form": form, "user_obj": u, "title": f"Change Password - {u.username}"})


@login_required
@user_passes_test(_staff_required)
def user_delete(request, pk: int):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    u = get_object_or_404(User, pk=pk)
    if request.user.pk == u.pk:
        messages.error(request, "You cannot delete your own account.")
        return redirect("orchestrator:user_list")
    if request.method == "POST":
        username = u.username
        u.delete()
        messages.success(request, f"Deleted user {username}.")
        return redirect("orchestrator:user_list")
    return render(request, "orchestrator/user_delete_confirm.html", {"user_obj": u})


@login_required
@user_passes_test(_staff_required)
def lease_log(request):
    # Filters
    q = (request.GET.get("q") or "").strip()
    event = (request.GET.get("event") or "").strip()
    user = (request.GET.get("user") or "").strip()
    server = (request.GET.get("server") or "").strip()
    start = (request.GET.get("start") or "").strip()
    end = (request.GET.get("end") or "").strip()

    # If LeaseLog table isn't present yet, render empty state with hint
    if "orchestrator_leaselog" not in connection.introspection.table_names():
        from django.core.paginator import Paginator
        empty = []
        paginator = Paginator(empty, 15)
        page_obj = paginator.get_page(1)
        servers = CMLServer.objects.order_by("name").values_list("name", flat=True)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        users = User.objects.order_by("username").values_list("username", flat=True)
        events = [e for e, _ in LeaseLog.EVENT_CHOICES]
        ctx = {
            "page_obj": page_obj,
            "events": events,
            "servers": servers,
            "users": users,
            "selected": {"q": q, "event": event, "user": user, "server": server, "start": start, "end": end},
            "missing_table": True,
            "qs_no_page": "",
        }
        return render(request, "orchestrator/lease_log.html", ctx)

    logs = LeaseLog.objects.select_related("user", "server").all()
    if event:
        logs = logs.filter(event=event)
    if user:
        logs = logs.filter(Q(username__iexact=user) | Q(user__username__iexact=user))
    if server:
        logs = logs.filter(Q(server_name__iexact=server) | Q(server__name__iexact=server))
    if q:
        logs = logs.filter(
            Q(lab_name__icontains=q)
            | Q(lab_uuid__icontains=q)
            | Q(username__icontains=q)
            | Q(server_name__icontains=q)
        )
    # Date filters (YYYY-MM-DD)
    try:
        if start:
            dt = timezone.datetime.fromisoformat(start)
            if dt.tzinfo is None:
                dt = timezone.make_aware(dt)
            logs = logs.filter(created_at__gte=dt)
    except Exception:
        pass
    try:
        if end:
            dt = timezone.datetime.fromisoformat(end)
            if dt.tzinfo is None:
                dt = timezone.make_aware(dt)
            logs = logs.filter(created_at__lte=dt)
    except Exception:
        pass

    # Pagination
    from django.core.paginator import Paginator

    paginator = Paginator(logs.order_by("-created_at"), 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    # Build querystring without page for pagination links
    qs_copy = request.GET.copy()
    qs_copy.pop("page", None)
    qs_no_page = qs_copy.urlencode()

    # For filter dropdowns
    servers = CMLServer.objects.order_by("name").values_list("name", flat=True)
    from django.contrib.auth import get_user_model

    User = get_user_model()
    users = User.objects.order_by("username").values_list("username", flat=True)
    events = [e for e, _ in LeaseLog.EVENT_CHOICES]

    ctx = {
        "page_obj": page_obj,
        "events": events,
        "servers": servers,
        "users": users,
        "selected": {
            "q": q,
            "event": event,
            "user": user,
            "server": server,
            "start": start,
            "end": end,
        },
        "qs_no_page": qs_no_page,
    }
    return render(request, "orchestrator/lease_log.html", ctx)


@login_required
def labs_upload(request):
    if request.method == "POST":
        form = LabUploadForm(request.POST, request.FILES)
        if form.is_valid():
            f = form.cleaned_data["yaml_file"]
            yaml_text = f.read().decode(errors="ignore")
            token = str(uuid.uuid4())
            request.session[f"lab_upload:{token}"] = yaml_text
            servers = CMLServer.objects.all().order_by("name")
            return render(request, "orchestrator/labs_upload_progress.html", {"servers": servers, "token": token})
    else:
        form = LabUploadForm()
    return render(request, "orchestrator/labs_upload.html", {"form": form})


@login_required
@csrf_exempt
def labs_upload_item(request, pk: int):
    server = get_object_or_404(CMLServer, pk=pk)
    token = request.GET.get("token") or request.POST.get("token")
    yaml_text = None
    if token:
        yaml_text = request.session.get(f"lab_upload:{token}")
    if not yaml_text:
        return render(request, "orchestrator/partials/upload_row.html", {"server": server, "status": "error", "message": "Upload token missing/expired."})
    result = push_lab_yaml_to_server(server, yaml_text)
    title = result.get("title") or "(unknown title)"
    if result.get("ok"):
        removed = result.get("removed") or 0
        msg = f"Uploaded lab '{title}'"
        if removed:
            msg += f"; removed {removed} duplicate(s)"
        return render(request, "orchestrator/partials/upload_row.html", {"server": server, "status": "ok", "message": msg, "log": []})
    else:
        msg = result.get("error") or "Upload failed"
        return render(request, "orchestrator/partials/upload_row.html", {"server": server, "status": "error", "message": f"{msg} (lab '{title}')"})


@login_required
def health_settings(request):
    hs = HealthSettings.get_solo()
    if request.method == "POST":
        form = HealthSettingsForm(request.POST)
        if form.is_valid():
            for field in (
                "mode",
                "check_interval_sec",
                "scheduler_tick_sec",
                "http_timeout_sec",
                "quick_retries",
                "quick_retry_delay_sec",
                "backoff_base_sec",
                "backoff_max_sec",
                "stats_interval_sec",
            ):
                setattr(hs, field, form.cleaned_data[field])
            hs.save()
            messages.success(request, "Health settings updated.")
            return redirect("orchestrator:health_settings")
    else:
        form = HealthSettingsForm(
            initial=dict(
                mode=hs.mode,
                check_interval_sec=hs.check_interval_sec,
                scheduler_tick_sec=hs.scheduler_tick_sec,
                http_timeout_sec=hs.http_timeout_sec,
                quick_retries=hs.quick_retries,
                quick_retry_delay_sec=hs.quick_retry_delay_sec,
                backoff_base_sec=hs.backoff_base_sec,
                backoff_max_sec=hs.backoff_max_sec,
                stats_interval_sec=hs.stats_interval_sec,
            )
        )
    return render(request, "orchestrator/health_settings.html", {"form": form})


@login_required
def pool_metrics(request):
    try:
        from .models import PoolStat
        stats = PoolStat.objects.all()[:200]
        total = CMLServer.objects.count()
        available = CMLServer.objects.filter(status=CMLServer.STATUS_AVAILABLE).count()
        return render(request, "orchestrator/pool_metrics.html", {"stats": stats, "pool_total": total, "pool_available": available})
    except Exception as e:
        # Attempt to create the table dynamically (dev convenience); else show guidance
        try:
            from django.db import connection
            from .models import PoolStat
            with connection.schema_editor() as se:
                se.create_model(PoolStat)
            # retry load after creating
            stats = PoolStat.objects.all()[:200]
            total = CMLServer.objects.count()
            available = CMLServer.objects.filter(status=CMLServer.STATUS_AVAILABLE).count()
            return render(request, "orchestrator/pool_metrics.html", {"stats": stats, "pool_total": total, "pool_available": available})
        except Exception as e2:
            return render(request, "orchestrator/pool_metrics_missing.html", {"error": str(e2)})


@login_required
def pool_metrics_data(request):
    """JSON time series for PoolStat to drive charts."""
    try:
        from .models import PoolStat
        qs = PoolStat.objects.order_by("created_at")
        # Time window filtering
        window = (request.GET.get("window") or "1h").lower()
        now = timezone.now()
        delta_map = {
            "15m": timezone.timedelta(minutes=15),
            "1h": timezone.timedelta(hours=1),
            "6h": timezone.timedelta(hours=6),
            "24h": timezone.timedelta(hours=24),
            "7d": timezone.timedelta(days=7),
        }
        if window in delta_map:
            start = now - delta_map[window]
            qs = qs.filter(created_at__gte=start)
        limit = int(request.GET.get("limit", 500))
        if limit > 0:
            total_count = qs.count()
            if total_count > limit:
                qs = qs[total_count - limit : total_count]
        labels = []
        available = []
        in_use = []
        unavailable = []
        initializing = []
        total = []
        for s in qs:
            labels.append(s.created_at.strftime("%Y-%m-%d %H:%M:%S"))
            total.append(s.total)
            available.append(s.available)
            in_use.append(s.in_use)
            unavailable.append(s.unavailable)
            initializing.append(s.initializing)
        return JsonResponse({
            "labels": labels,
            "series": {
                "total": total,
                "available": available,
                "in_use": in_use,
                "unavailable": unavailable,
                "initializing": initializing,
            }
        })
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def server_row(request, pk: int):
    server = get_object_or_404(CMLServer, pk=pk)
    return render(request, "orchestrator/partials/server_row.html", {"s": server})


@login_required
def pool_counts(request):
    """Return a small HTML snippet with current pool availability counts.
    Used by HTMX on the home page header to refresh numbers.
    """
    servers = CMLServer.objects.all()
    ctx = {
        "pool_total": servers.count(),
        "pool_available": servers.filter(status=CMLServer.STATUS_AVAILABLE).count(),
    }
    return render(request, "orchestrator/partials/pool_counts.html", ctx)


@csrf_exempt
def api_assign(request):
    """API: Assign a user to a lab via the pool and return server IP.
    Request: POST JSON or form-encoded with keys: username (or user), lab (or lab_name), optional minutes
    Response: 200 text/plain body with the server IP, or JSON error with status 4xx/5xx.
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    # Parse payload
    data = {}
    ctype = (request.content_type or "").lower()
    if "application/json" in ctype:
        try:
            data = json.loads(request.body.decode() or "{}")
        except Exception:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
    else:
        data = request.POST

    username = (data.get("username") or data.get("user") or "").strip()
    lab = (data.get("lab") or data.get("lab_name") or "").strip()
    minutes_raw = data.get("minutes")
    try:
        minutes = int(minutes_raw) if minutes_raw is not None else 60
    except Exception:
        return JsonResponse({"error": "Invalid minutes"}, status=400)

    if not username:
        return JsonResponse({"error": "Missing 'username'"}, status=400)
    if not lab:
        return JsonResponse({"error": "Missing 'lab'"}, status=400)

    # Get or create user
    try:
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"is_staff": False, "is_superuser": False},
        )
        if created:
            user.set_unusable_password()
            user.save(update_fields=["password"])
    except Exception as e:
        return JsonResponse({"error": f"User error: {e}"}, status=400)

    # Assign via pool
    try:
        server = assign_via_pool(user, lab, minutes=minutes)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

    # Resolve IP from server.base_url
    try:
        host = urlsplit(server.base_url).hostname or ""
        ip_str = None
        if host:
            try:
                ipaddress.ip_address(host)  # already an IP
                ip_str = host
            except ValueError:
                infos = socket.getaddrinfo(host, None)
                # Prefer IPv4
                for fam, _, _, _, sockaddr in infos:
                    if fam == socket.AF_INET:
                        ip_str = sockaddr[0]
                        break
                if not ip_str and infos:
                    ip_str = infos[0][4][0]
        if not ip_str:
            return JsonResponse({"error": "Unable to resolve server IP"}, status=502)
        return HttpResponse(ip_str, content_type="text/plain")
    except Exception as e:
        return JsonResponse({"error": f"IP resolution failed: {e}"}, status=502)


@csrf_exempt
def api_release(request):
    """API: Release a user's CML assignment.
    Request: POST JSON or form with key: username (or user)
    Response: 200 text/plain: "OK" if released, "NONE" if no assignment; JSON error on failure.
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    # Parse payload
    data = {}
    ctype = (request.content_type or "").lower()
    if "application/json" in ctype:
        try:
            data = json.loads(request.body.decode() or "{}")
        except Exception:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
    else:
        data = request.POST

    username = (data.get("username") or data.get("user") or "").strip()
    if not username:
        return JsonResponse({"error": "Missing 'username'"}, status=400)

    # Resolve user
    try:
        from django.contrib.auth import get_user_model

        User = get_user_model()
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return JsonResponse({"error": "User not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": f"User error: {e}"}, status=400)

    # Find and release assignment
    from .services import get_user_assignment

    server = get_user_assignment(user)
    if not server:
        return HttpResponse("NONE", content_type="text/plain")
    try:
        release_server(server)
        return HttpResponse("OK", content_type="text/plain")
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def api_assign(request):
    """API: Assign a user to a lab via the pool and return server IP.
    Request: POST JSON or form-encoded with keys: username (or user), lab (or lab_name), optional minutes
    Response: 200 text/plain body with the server IP, or JSON error with status 4xx/5xx.
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    # Parse payload
    data = {}
    ctype = (request.content_type or "").lower()
    if "application/json" in ctype:
        try:
            data = json.loads(request.body.decode() or "{}")
        except Exception:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
    else:
        data = request.POST

    username = (data.get("username") or data.get("user") or "").strip()
    lab = (data.get("lab") or data.get("lab_name") or "").strip()
    minutes_raw = data.get("minutes")
    try:
        minutes = int(minutes_raw) if minutes_raw is not None else 60
    except Exception:
        return JsonResponse({"error": "Invalid minutes"}, status=400)

    if not username:
        return JsonResponse({"error": "Missing 'username'"}, status=400)
    if not lab:
        return JsonResponse({"error": "Missing 'lab'"}, status=400)

    # Get or create user
    try:
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"is_staff": False, "is_superuser": False},
        )
        if created:
            user.set_unusable_password()
            user.save(update_fields=["password"])
    except Exception as e:
        return JsonResponse({"error": f"User error: {e}"}, status=400)

    # Assign via pool
    try:
        server = assign_via_pool(user, lab, minutes=minutes)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

    # Resolve IP from server.base_url
    try:
        host = urlsplit(server.base_url).hostname or ""
        ip_str = None
        if host:
            try:
                ipaddress.ip_address(host)  # already an IP
                ip_str = host
            except ValueError:
                infos = socket.getaddrinfo(host, None)
                # Prefer IPv4
                for fam, _, _, _, sockaddr in infos:
                    if fam == socket.AF_INET:
                        ip_str = sockaddr[0]
                        break
                if not ip_str and infos:
                    ip_str = infos[0][4][0]
        if not ip_str:
            return JsonResponse({"error": "Unable to resolve server IP"}, status=502)
        return HttpResponse(ip_str, content_type="text/plain")
    except Exception as e:
        return JsonResponse({"error": f"IP resolution failed: {e}"}, status=502)
