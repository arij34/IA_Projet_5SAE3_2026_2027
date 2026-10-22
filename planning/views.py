from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from projects.permissions import IsProjectOwner

from .ai.generation import generate_tasks
from .models import PlanningProject, Task
from .serializers import (
    GeneratePlanningSerializer,
    PlanningProjectCreateSerializer,
    PlanningProjectReadSerializer,
    TaskReadSerializer,
    TaskWriteSerializer,
)


class GeneratePlanningView(APIView):
    permission_classes = (IsProjectOwner,)

    def post(self, request):
        request_serializer = GeneratePlanningSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        tasks, simulated = generate_tasks(request_serializer.validated_data["project_name"])
        return Response({"tasks": tasks, "simulated": simulated})


class PlanningProjectListCreateView(generics.ListCreateAPIView):
    permission_classes = (IsProjectOwner,)

    def get_queryset(self):
        return PlanningProject.objects.filter(owner=self.request.user).prefetch_related("tasks")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return PlanningProjectCreateSerializer
        return PlanningProjectReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        project = serializer.save()
        return Response(
            PlanningProjectReadSerializer(project, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )


class PlanningProjectDetailView(generics.RetrieveAPIView):
    serializer_class = PlanningProjectReadSerializer
    permission_classes = (IsProjectOwner,)

    def get_queryset(self):
        return PlanningProject.objects.filter(owner=self.request.user).prefetch_related("tasks")


class PlanningTaskDetailView(APIView):
    permission_classes = (IsProjectOwner,)

    def get_task(self, request, project_id, task_id):
        return get_object_or_404(
            Task.objects.select_related("project"),
            pk=task_id,
            project_id=project_id,
            project__owner=request.user,
        )

    def put(self, request, project_id, task_id):
        return self._update(request, project_id, task_id, partial=False)

    def patch(self, request, project_id, task_id):
        return self._update(request, project_id, task_id, partial=True)

    def _update(self, request, project_id, task_id, partial):
        task = self.get_task(request, project_id, task_id)
        serializer = TaskWriteSerializer(task, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(TaskReadSerializer(task).data)

    def delete(self, request, project_id, task_id):
        task = self.get_task(request, project_id, task_id)
        task.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
