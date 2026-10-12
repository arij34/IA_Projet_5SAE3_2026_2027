"""Tests de gestion des CV privés."""

import tempfile
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from users.models import User


class CvApiTests(TestCase):
    """Vérifie les accès utilisateur et administrateur aux CV privés."""

    url = "/api/users/me/cv/"

    def setUp(self) -> None:
        """Prépare deux utilisateurs et un stockage privé temporaire."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            "cv-user",
            "cv-user@example.com",
            "motdepasse123",
            moderation_status=User.ModerationStatus.PENDING,
        )
        self.other_user = User.objects.create_user(
            "other-cv-user",
            "other-cv-user@example.com",
            "motdepasse123",
            moderation_status=User.ModerationStatus.OK,
        )
        self.admin = User.objects.create_superuser(
            "cv-admin",
            "cv-admin@example.com",
            "motdepasse123",
        )
        self.temp_dir = tempfile.TemporaryDirectory()
        self.storage = User._meta.get_field("cv").storage
        self.old_location = self.storage._location
        self.storage._location = Path(self.temp_dir.name)
        self.addCleanup(self._cleanup_storage)

    def _cleanup_storage(self) -> None:
        """Restaure le stockage global et supprime le répertoire temporaire."""
        self.storage._location = self.old_location
        self.temp_dir.cleanup()

    def authenticate(self, user: User) -> None:
        """Authentifie le client avec l'utilisateur fourni."""
        self.client.force_authenticate(user=user)

    def upload(self, name: str = "cv.pdf", content: bytes = b"%PDF-1.7\nCV") -> None:
        """Envoie un fichier CV au format multipart."""
        response = self.client.post(
            self.url,
            {"cv": SimpleUploadedFile(name, content, content_type="application/pdf")},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_valid_pdf_returns_201_and_has_cv(self) -> None:
        """Un PDF valide est enregistré sans exposer d'URL."""
        self.authenticate(self.user)

        response = self.client.post(
            self.url,
            {
                "cv": SimpleUploadedFile(
                    "nom-original.pdf",
                    b"%PDF-1.7\ncontenu",
                    content_type="application/pdf",
                )
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data, {"has_cv": True})
        self.user.refresh_from_db()
        self.assertTrue(self.user.cv.name.startswith("cv/"))
        self.assertNotIn("nom-original", self.user.cv.name)

    def test_renamed_non_pdf_is_rejected(self) -> None:
        """Un fichier non PDF renommé en .pdf est refusé."""
        self.authenticate(self.user)

        response = self.client.post(
            self.url,
            {"cv": SimpleUploadedFile("faux.pdf", b"not-a-pdf")},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_file_over_five_mo_is_rejected(self) -> None:
        """Un CV dépassant cinq mégaoctets est refusé."""
        self.authenticate(self.user)

        response = self.client.post(
            self.url,
            {
                "cv": SimpleUploadedFile(
                    "grand.pdf",
                    b"%PDF-" + b"x" * (5 * 1024 * 1024),
                )
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_user_returns_401(self) -> None:
        """Un utilisateur non connecté ne peut pas gérer un CV."""
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_cannot_access_another_user_cv(self) -> None:
        """Le téléchargement utilisateur reste limité au compte connecté."""
        self.authenticate(self.other_user)
        self.upload()
        self.client.force_authenticate(user=self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_non_admin_returns_403_on_admin_endpoint(self) -> None:
        """Un utilisateur non administrateur ne peut pas utiliser la route admin."""
        self.authenticate(self.user)

        response = self.client.get(f"/api/admin/users/{self.other_user.id}/cv/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_replacement_deletes_previous_file(self) -> None:
        """Le remplacement supprime physiquement l'ancien CV."""
        self.authenticate(self.user)
        self.upload(content=b"%PDF-1.4\nancien")
        self.user.refresh_from_db()
        old_path = Path(self.user.cv.path)

        self.upload(content=b"%PDF-1.7\nnouveau")
        self.user.refresh_from_db()

        self.assertFalse(old_path.exists())
        self.assertTrue(Path(self.user.cv.path).exists())

    def test_delete_removes_cv(self) -> None:
        """La suppression efface le fichier et la référence en base."""
        self.authenticate(self.user)
        self.upload()
        self.user.refresh_from_db()
        cv_path = Path(self.user.cv.path)

        response = self.client.delete(self.url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.user.refresh_from_db()
        self.assertFalse(self.user.cv)
        self.assertFalse(cv_path.exists())

    def test_admin_can_download_user_cv(self) -> None:
        """Un administrateur peut télécharger le CV d'un utilisateur."""
        self.authenticate(self.user)
        self.upload()
        self.authenticate(self.admin)

        response = self.client.get(f"/api/admin/users/{self.user.id}/cv/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertEqual(response.streaming_content.__next__(), b"%PDF-1.7\nCV")
        response.close()
