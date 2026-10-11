from django.db import migrations, models


class Migration(migrations.Migration):
    """Ajoute les critères détaillés à l'historique de modération."""

    dependencies = [
        ("users", "0002_moderationlog"),
    ]

    operations = [
        migrations.AddField(
            model_name="moderationlog",
            name="criteria",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
