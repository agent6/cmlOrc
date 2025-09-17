from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("orchestrator", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="LeaseLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("event", models.CharField(choices=[("leased", "Leased"), ("extended", "Extended"), ("lab_started", "Lab Started"), ("released", "Released")], max_length=20)),
                ("username", models.CharField(blank=True, max_length=150)),
                ("server_name", models.CharField(blank=True, max_length=100)),
                ("lab_uuid", models.CharField(blank=True, max_length=64)),
                ("lab_name", models.CharField(blank=True, max_length=255)),
                ("minutes", models.PositiveIntegerField(blank=True, null=True)),
                ("server", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lease_logs", to="orchestrator.cmlserver")),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="lease_logs", to="auth.user")),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["created_at"], name="orchestrat_created_0f3331_idx"),
                    models.Index(fields=["event"], name="orchestrat_event_6ea86c_idx"),
                    models.Index(fields=["username"], name="orchestrat_usernam_f2f9d9_idx"),
                    models.Index(fields=["server_name"], name="orchestrat_server__a6aa1f_idx"),
                ],
            },
        ),
    ]
