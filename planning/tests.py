import json
from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from users.ai.exceptions import LLMTimeoutError

from .models import PlanningProject, Task


User = get_user_model()


def generated_tasks(start: date | None = None):
    current = start or timezone.localdate()
    tasks = []
    for name in ("Project discovery", "Solution design", "Build and review"):
        end = current + timedelta(days=2)
        tasks.append(
            {
                "name": name,
                "description": f"Complete {name.lower()} for this project.",
                "start_date": current.isoformat(),
                "end_date": end.isoformat(),
            }
        )
        current = end + timedelta(days=1)
    return tasks


class PlanningApiTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="planning-owner",
            email="planning-owner@example.test",
            password="test-password-123",
            role="PROJECT_OWNER",
        )
        self.other_user = User.objects.create_user(
            username="other-owner",
            email="other-owner@example.test",
            password="test-password-123",
            role="PROJECT_OWNER",
        )
        self.freelancer = User.objects.create_user(
            username="planning-freelancer",
            email="planning-freelancer@example.test",
            password="test-password-123",
            role="FREELANCER",
        )
        self.client.force_authenticate(self.owner)

    @override_settings(LLM_PROVIDER="gemini")
    @patch("planning.ai.generation.call_llm")
    def test_valid_generation_returns_three_valid_tasks_and_saves_nothing(self, call_llm):
        call_llm.return_value = "```json\n" + json.dumps({"tasks": generated_tasks()}) + "\n```"
        response = self.client.post(
            "/api/planning/generate/",
            {"project_name": "DevOps project"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["simulated"])
        self.assertEqual(len(response.data["tasks"]), 3)
        for index, task in enumerate(response.data["tasks"]):
            self.assertEqual(
                set(task), {"name", "description", "start_date", "end_date"}
            )
            start = date.fromisoformat(task["start_date"])
            end = date.fromisoformat(task["end_date"])
            self.assertGreaterEqual((end - start).days + 1, 3)
            self.assertLessEqual((end - start).days + 1, 7)
            if index == 0:
                self.assertEqual(start, timezone.localdate())
            else:
                previous_end = date.fromisoformat(response.data["tasks"][index - 1]["end_date"])
                self.assertEqual(start, previous_end + timedelta(days=1))
        self.assertEqual(PlanningProject.objects.count(), 0)
        self.assertEqual(Task.objects.count(), 0)
        call_llm.assert_called_once()
        self.assertEqual(call_llm.call_args.args[1], "DevOps project")

    @override_settings(LLM_PROVIDER="gemini")
    @patch("planning.ai.generation.call_llm", return_value="not JSON")
    def test_invalid_llm_json_returns_safe_fallback(self, _call_llm):
        response = self.client.post(
            "/api/planning/generate/",
            {"project_name": "Website redesign"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["simulated"])
        self.assertEqual(len(response.data["tasks"]), 3)
        self.assertEqual(response.data["tasks"][0]["name"], "Project discovery")

    @override_settings(LLM_PROVIDER="gemini")
    @patch("planning.ai.generation.call_llm", side_effect=LLMTimeoutError("timeout"))
    def test_provider_failure_returns_fallback(self, _call_llm):
        response = self.client.post(
            "/api/planning/generate/",
            {"project_name": "Projet DevOps"},
            format="json",
        )
        self.assertTrue(response.data["simulated"])
        self.assertEqual(len(response.data["tasks"]), 3)
        self.assertEqual(response.data["tasks"][0]["name"], "Cadrage du projet")

    @override_settings(LLM_PROVIDER="mock")
    def test_mock_provider_returns_simulated_tasks(self):
        response = self.client.post(
            "/api/planning/generate/",
            {"project_name": "Projet DevOps"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["simulated"])
        self.assertEqual(len(response.data["tasks"]), 3)

    def test_generation_rejects_empty_and_long_project_names(self):
        empty = self.client.post("/api/planning/generate/", {"project_name": " "}, format="json")
        long_name = self.client.post(
            "/api/planning/generate/", {"project_name": "x" * 101}, format="json"
        )
        self.assertEqual(empty.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(long_name.status_code, status.HTTP_400_BAD_REQUEST)

    def test_generation_requires_authentication(self):
        self.client.force_authenticate(user=None)
        response = self.client.post(
            "/api/planning/generate/", {"project_name": "DevOps"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_freelancer_role_cannot_use_project_owner_planning_api(self):
        self.client.force_authenticate(self.freelancer)
        response = self.client.post(
            "/api/planning/generate/", {"project_name": "DevOps"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_invalid_task_names_and_dates_are_rejected(self):
        invalid_name = generated_tasks()
        invalid_name[0]["name"] = "No"
        response_name = self.client.post(
            "/api/planning/", {"name": "Planning", "tasks": invalid_name}, format="json"
        )
        invalid_dates = generated_tasks()
        invalid_dates[0]["end_date"] = (timezone.localdate() - timedelta(days=1)).isoformat()
        response_date = self.client.post(
            "/api/planning/", {"name": "Planning", "tasks": invalid_dates}, format="json"
        )
        self.assertEqual(response_name.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response_date.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(PlanningProject.objects.count(), 0)

    def test_saving_persists_project_and_tasks_atomically(self):
        response = self.client.post(
            "/api/planning/", {"name": "DevOps", "tasks": generated_tasks()}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(PlanningProject.objects.count(), 1)
        self.assertEqual(Task.objects.filter(project__owner=self.owner).count(), 3)
        self.assertEqual(response.data["name"], "DevOps")

    def test_list_and_retrieve_only_return_the_current_users_plannings(self):
        own = PlanningProject.objects.create(owner=self.owner, name="My plan")
        PlanningProject.objects.create(owner=self.other_user, name="Private plan")
        list_response = self.client.get("/api/planning/")
        detail_response = self.client.get(f"/api/planning/{own.id}/")
        hidden_response = self.client.get(
            f"/api/planning/{PlanningProject.objects.get(name='Private plan').id}/"
        )
        self.assertEqual([item["name"] for item in list_response.data], ["My plan"])
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(hidden_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_task_update_and_delete_work(self):
        project = PlanningProject.objects.create(owner=self.owner, name="DevOps")
        task = Task.objects.create(
            project=project,
            name="Project discovery",
            description="Clarify project goals.",
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timedelta(days=2),
        )
        update_response = self.client.patch(
            f"/api/planning/{project.id}/tasks/{task.id}/",
            {"name": "Updated discovery"},
            format="json",
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data["name"], "Updated discovery")
        delete_response = self.client.delete(f"/api/planning/{project.id}/tasks/{task.id}/")
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Task.objects.filter(pk=task.pk).exists())
