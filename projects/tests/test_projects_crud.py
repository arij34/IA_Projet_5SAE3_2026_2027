"""Tests du CRUD des projets."""

from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from projects.models import Project
from users.models import User


class ProjectCrudTests(TestCase):
    """Vérifie le CRUD et les protections du modèle Project."""

    url = "/api/projects/"

    def setUp(self) -> None:
        """Prépare deux porteurs et un freelance."""
        self.client = APIClient()
        self.owner = User.objects.create_user(
            "owner",
            "owner@example.com",
            "motdepasse123",
            role=User.Role.PROJECT_OWNER,
        )
        self.other_owner = User.objects.create_user(
            "other-owner",
            "other-owner@example.com",
            "motdepasse123",
            role=User.Role.PROJECT_OWNER,
        )
        self.freelancer = User.objects.create_user(
            "freelancer",
            "freelancer@example.com",
            "motdepasse123",
            role=User.Role.FREELANCER,
        )
        self.project = Project.objects.create(
            owner=self.owner,
            name="Projet initial",
            description="Description initiale",
            deadline=date.today() + timedelta(days=10),
            estimated_amount=Decimal("1000.00"),
            status=Project.Status.PUBLISHED,
        )

    def authenticate(self, user: User) -> None:
        """Authentifie le client avec l'utilisateur fourni."""
        self.client.force_authenticate(user=user)

    def payload(self, **overrides) -> dict:
        """Construit une charge utile valide pour les tests."""
        data = {
            "name": "Nouveau projet",
            "description": "Description du nouveau projet",
            "deadline": str(date.today() + timedelta(days=30)),
            "estimated_amount": "2500.00",
        }
        data.update(overrides)
        return data

    def test_owner_can_create_project(self) -> None:
        """Un porteur authentifié peut créer un projet qui lui appartient."""
        self.authenticate(self.owner)

        response = self.client.post(self.url, self.payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = Project.objects.get(name="Nouveau projet")
        self.assertEqual(created.owner, self.owner)
        self.assertEqual(created.status, Project.Status.DRAFT)

    def test_owner_can_list_and_retrieve_own_projects(self) -> None:
        """Un porteur ne reçoit que ses projets."""
        self.authenticate(self.owner)

        list_response = self.client.get(self.url)
        detail_response = self.client.get(f"{self.url}{self.project.pk}/")

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data), 1)
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)

    def test_owner_can_patch_and_delete_project(self) -> None:
        """Un porteur peut modifier partiellement puis supprimer son projet."""
        self.authenticate(self.owner)

        patch_response = self.client.patch(
            f"{self.url}{self.project.pk}/",
            {"name": "Nom modifié"},
            format="json",
        )
        delete_response = self.client.delete(f"{self.url}{self.project.pk}/")

        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Project.objects.filter(pk=self.project.pk).exists())

    def test_put_is_not_allowed(self) -> None:
        """Le remplacement complet par PUT est interdit."""
        self.authenticate(self.owner)

        response = self.client.put(
            f"{self.url}{self.project.pk}/",
            self.payload(),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_freelancer_cannot_create_project(self) -> None:
        """Un freelance ne peut pas créer de projet."""
        self.authenticate(self.freelancer)

        response = self.client.post(self.url, self.payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_cannot_access_another_owner_project(self) -> None:
        """Un porteur obtient 404 pour le projet d'un autre porteur."""
        self.authenticate(self.other_owner)

        response = self.client.get(f"{self.url}{self.project.pk}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_status_sent_in_post_is_ignored(self) -> None:
        """Le statut transmis par le client ne modifie pas le statut initial."""
        self.authenticate(self.owner)

        response = self.client.post(
            self.url,
            self.payload(status=Project.Status.PUBLISHED, owner=self.other_owner.pk),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = Project.objects.get(name="Nouveau projet")
        self.assertEqual(created.status, Project.Status.DRAFT)
        self.assertEqual(created.owner, self.owner)

    def test_past_deadline_is_rejected(self) -> None:
        """Une échéance passée est refusée."""
        self.authenticate(self.owner)

        response = self.client.post(
            self.url,
            self.payload(deadline=str(date.today())),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_negative_amount_is_rejected(self) -> None:
        """Un montant négatif est refusé."""
        self.authenticate(self.owner)

        response = self.client.post(
            self.url,
            self.payload(estimated_amount="-1.00"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_description_change_resets_status_to_draft(self) -> None:
        """Une modification de description remet le projet en brouillon."""
        self.authenticate(self.owner)

        response = self.client.patch(
            f"{self.url}{self.project.pk}/",
            {"description": "Description modifiée"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.DRAFT)
