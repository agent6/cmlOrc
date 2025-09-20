from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orchestrator", "0008_alter_cmlserver_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="poolstat",
            name="maintenance",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
