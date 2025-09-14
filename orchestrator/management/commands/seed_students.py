from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = "Create N test student users (non-admin). Default: 4"

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=4, help="How many students to create")
        parser.add_argument("--prefix", type=str, default="student", help="Username prefix")
        parser.add_argument("--password", type=str, default="changeme", help="Password to set")

    def handle(self, *args, **opts):
        User = get_user_model()
        count = max(1, int(opts["count"]))
        prefix = opts["prefix"].strip() or "student"
        password = opts["password"]
        created = []
        skipped = []
        idx = 1
        while len(created) < count:
            username = f"{prefix}{idx:02d}"
            if not User.objects.filter(username=username).exists():
                u = User(username=username, is_staff=False, is_superuser=False)
                u.set_password(password)
                u.save()
                created.append(username)
            else:
                skipped.append(username)
            idx += 1

        if created:
            self.stdout.write(self.style.SUCCESS(f"Created {len(created)}: {', '.join(created)}"))
            self.stdout.write(self.style.WARNING(f"Default password: {password}"))
        if skipped:
            self.stdout.write(f"Skipped existing: {', '.join(skipped)}")

