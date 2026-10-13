"""Tests de la présentation statique de l'application."""

from django.test import SimpleTestCase

from projects.ai.app_overview import APP_OVERVIEW, MAX_OVERVIEW_CHARS


class AppOverviewTests(SimpleTestCase):
    """Vérifie les limites de la présentation de l'application."""

    def test_app_overview_exists_and_respects_limit(self) -> None:
        """La présentation existe et ne dépasse pas la longueur autorisée."""
        self.assertIsInstance(APP_OVERVIEW, str)
        self.assertTrue(APP_OVERVIEW)
        self.assertLessEqual(len(APP_OVERVIEW), MAX_OVERVIEW_CHARS)
