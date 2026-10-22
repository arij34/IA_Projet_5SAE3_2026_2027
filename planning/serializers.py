from django.db import transaction
from rest_framework import serializers

from .models import PlanningProject, Task


class TaskWriteSerializer(serializers.ModelSerializer):
    start_date = serializers.DateField(input_formats=("%Y-%m-%d",))
    end_date = serializers.DateField(input_formats=("%Y-%m-%d",))

    class Meta:
        model = Task
        fields = ("name", "description", "start_date", "end_date")
        extra_kwargs = {
            "name": {"min_length": 3, "max_length": 100, "trim_whitespace": True},
            "description": {"allow_blank": False, "trim_whitespace": True},
        }

    def validate(self, attrs):
        start_date = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end_date = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError(
                {"end_date": "La date de fin doit être égale ou postérieure à la date de début."}
            )
        return attrs


class TaskReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ("id", "name", "description", "start_date", "end_date")


class PlanningProjectReadSerializer(serializers.ModelSerializer):
    tasks = TaskReadSerializer(many=True, read_only=True)

    class Meta:
        model = PlanningProject
        fields = ("id", "name", "created_at", "tasks")


class PlanningProjectCreateSerializer(serializers.Serializer):
    name = serializers.CharField(min_length=1, max_length=100, trim_whitespace=True)
    tasks = TaskWriteSerializer(many=True, required=True)

    def create(self, validated_data):
        tasks_data = validated_data.pop("tasks")
        with transaction.atomic():
            project = PlanningProject.objects.create(
                owner=self.context["request"].user,
                **validated_data,
            )
            Task.objects.bulk_create(
                Task(project=project, **task_data) for task_data in tasks_data
            )
        return project


class GeneratePlanningSerializer(serializers.Serializer):
    project_name = serializers.CharField(
        min_length=1,
        max_length=100,
        trim_whitespace=True,
        error_messages={
            "blank": "Le nom du projet est obligatoire.",
            "max_length": "Le nom du projet ne peut pas dépasser 100 caractères.",
        },
    )
