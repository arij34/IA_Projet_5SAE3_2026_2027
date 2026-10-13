"""Tests des décisions du porteur et de la liste publique."""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from projects.models import Project, ProjectAnalysis


class DecisionAndPublicTests(TestCase):
    """Vérifie les décisions et la diffusion contrôlée des projets publiés."""

    def setUp(self) -> None:
        """Prépare des porteurs approuvés et plusieurs projets."""
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            username="decision-owner",
            email="decision-owner@example.com",
            password="motdepasse123",
            role="PROJECT_OWNER",
            moderation_status="OK",
        )
        self.other_owner = user_model.objects.create_user(
            username="decision-other",
            email="decision-other@example.com",
            password="motdepasse123",
            role="PROJECT_OWNER",
            moderation_status="OK",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.owner)
        self.project = self.create_project(Project.Status.DRAFT)

    def create_project(self, project_status: str) -> Project:
        """Crée un projet appartenant au porteur de test."""
        return Project.objects.create(
            owner=self.owner,
            name=f"Projet {project_status}",
            description="Description détaillée du projet.",
            deadline=date.today() + timedelta(days=30),
            estimated_amount=Decimal("5000.00"),
            status=project_status,
        )

    def add_successful_analysis(self, project: Project) -> None:
        """Ajoute une analyse réussie avec des champs privés."""
        ProjectAnalysis.objects.create(
            project=project,
            result={
                "budget_min": 4000,
                "budget_max": 6000,
                "devise": "EUR",
                "nb_freelancers": 2,
                "specialites": [{"nom": "Web", "nb": 1}],
                "duree_semaines": 8,
                "complexite": "MOYENNE",
                "risques": ["Risque privé"],
                "jalons": ["Cadrage", "Recette"],
                "recommandation": "Recommandation privée",
                "coherence_budget": "COHERENT",
                "confiance": 0.9,
            },
        )

    def decision_url(self, action: str, project=None) -> str:
        """Construit l'URL d'une décision."""
        return f"/api/projects/{(project or self.project).pk}/{action}/"

    def test_publishing_draft_returns_409(self) -> None:
        """Un brouillon ne peut pas être publié."""
        response = self.client.post(self.decision_url("publish"))
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_publishing_analyzed_project_succeeds(self) -> None:
        """Un projet analysé avec succès devient publié."""
        self.project.status = Project.Status.ANALYZED
        self.project.save(update_fields=("status",))
        self.add_successful_analysis(self.project)

        response = self.client.post(self.decision_url("publish"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.PUBLISHED)

    def test_other_owner_cannot_publish(self) -> None:
        """Le projet d'un autre porteur est masqué par un 404."""
        self.client.force_authenticate(user=self.other_owner)

        response = self.client.post(self.decision_url("publish"))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_publishing_failed_analysis_returns_409(self) -> None:
        """Une analyse en erreur ne permet pas la publication."""
        self.project.status = Project.Status.ANALYZED
        self.project.save(update_fields=("status",))
        ProjectAnalysis.objects.create(
            project=self.project,
            error="Analyse indisponible",
        )

        response = self.client.post(self.decision_url("publish"))

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_declining_analyzed_project_succeeds(self) -> None:
        """Un projet analysé avec succès peut être refusé."""
        self.project.status = Project.Status.ANALYZED
        self.project.save(update_fields=("status",))
        self.add_successful_analysis(self.project)

        response = self.client.post(self.decision_url("decline"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.DECLINED)

    def test_published_project_appears_publicly(self) -> None:
        """Un projet publié apparaît avec sa synthèse publique."""
        self.project.status = Project.Status.PUBLISHED
        self.project.save(update_fields=("status",))
        self.add_successful_analysis(self.project)

        response = self.client.get("/api/projects/published/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        item = response.data["results"][0]
        self.assertEqual(item["id"], self.project.pk)
        self.assertEqual(item["analysis"]["budget_min"], 4000)

    def test_non_published_projects_are_hidden(self) -> None:
        """Les projets DRAFT, ANALYZED et DECLINED sont exclus."""
        for project_status in (
            Project.Status.ANALYZED,
            Project.Status.DECLINED,
        ):
            project = self.create_project(project_status)
            self.add_successful_analysis(project)

        response = self.client.get("/api/projects/published/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_public_json_has_no_owner_or_private_analysis_fields(self) -> None:
        """La réponse publique ne révèle ni propriétaire ni analyse privée."""
        self.project.status = Project.Status.PUBLISHED
        self.project.save(update_fields=("status",))
        self.add_successful_analysis(self.project)

        response = self.client.get("/api/projects/published/")
        item = response.data["results"][0]

        self.assertNotIn("owner", item)
        self.assertNotIn("email", item)
        self.assertNotIn("username", item)
        self.assertNotIn("risques", item["analysis"])
        self.assertNotIn("jalons", item["analysis"])
        self.assertNotIn("recommandation", item["analysis"])
        self.assertNotIn("error", item["analysis"])

    def test_owner_status_filter_accepts_valid_value(self) -> None:
        """Le filtre status limite la liste du propriétaire."""
        self.create_project(Project.Status.ANALYZED)

        response = self.client.get("/api/projects/?status=ANALYZED")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["status"], Project.Status.ANALYZED)

    def test_owner_status_filter_rejects_unknown_value(self) -> None:
        """Une valeur de statut inconnue est rejetée."""
        response = self.client.get("/api/projects/?status=UNKNOWN")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_published_project_cannot_change_business_fields(self) -> None:
        """La description, l'échéance et le montant sont verrouillés après publication."""
        self.project.status = Project.Status.PUBLISHED
        self.project.save(update_fields=("status",))

        response = self.client.patch(
            f"/api/projects/{self.project.pk}/",
            {"description": "Nouvelle description"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
