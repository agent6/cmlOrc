from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Run a one-shot sweep to release expired leases. Useful for debugging worker."

    def handle(self, *args, **opts):
        from orchestrator.services import check_and_release_expired_leases

        check_and_release_expired_leases()
        self.stdout.write(self.style.SUCCESS("Lease sweep executed."))

