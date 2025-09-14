import os
import sys
from django.apps import AppConfig
from django.conf import settings


class OrchestratorConfig(AppConfig):
    name = "orchestrator"
    verbose_name = "CML Orchestrator"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        # Skip worker when running management commands that alter/inspect DB
        mgmt_cmds = {
            "makemigrations",
            "migrate",
            "collectstatic",
            "shell",
            "createsuperuser",
            "dbshell",
            "dumpdata",
            "loaddata",
            "changepassword",
            "test",
            "flush",
            "showmigrations",
            "check",
            "sqlmigrate",
        }
        if any(cmd in sys.argv for cmd in mgmt_cmds):
            return

        # Determine if worker should run in this process:
        # - Always for 'runserver'
        # - Otherwise only if RUN_BACKGROUND_WORKER=1 is explicitly set
        allow_worker = False
        if any(arg == "runserver" for arg in sys.argv):
            allow_worker = True
        elif getattr(settings, "RUN_BACKGROUND_WORKER", False):
            allow_worker = True

        if allow_worker:
            try:
                from .worker import ensure_worker_running

                ensure_worker_running()
            except Exception:
                pass

