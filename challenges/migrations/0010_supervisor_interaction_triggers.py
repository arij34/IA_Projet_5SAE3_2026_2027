from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("challenges", "0009_question_interactions")]

    operations = [
        migrations.AlterField(
            model_name="supervisorevent",
            name="trigger_type",
            field=models.CharField(
                max_length=24,
                choices=[
                    ("repeated_errors", "Repeated errors"),
                    ("positive_feedback", "Positive feedback"),
                    ("slow_progress", "Slow progress"),
                    ("repeated_answer_changes", "Repeated answer changes"),
                    ("long_response", "Long response"),
                    ("multiple_timeouts", "Multiple timeouts"),
                ],
            ),
        ),
    ]
