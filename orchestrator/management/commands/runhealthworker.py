import time
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Run the background health/lease worker (one instance only)."

    def add_arguments(self, parser):
        parser.add_argument("--tick", type=int, default=None, help="Override scheduler tick (sec)")

    def handle(self, *args, **opts):
        from django.conf import settings
        from orchestrator.worker import ensure_worker_running

        ensure_worker_running()
        tick = opts.get("tick") or getattr(settings, "HEALTH_SCHEDULER_TICK", 1)
        self.stdout.write(self.style.SUCCESS(f"Health worker running (tick={tick}s)… Press Ctrl+C to stop."))
        try:
            while True:
                time.sleep(tick)
        except KeyboardInterrupt:
            self.stdout.write("Shutting down worker…")

