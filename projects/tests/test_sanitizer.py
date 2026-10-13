"""Tests du nettoyage des textes de projets."""

from django.test import SimpleTestCase

from projects.ai.sanitizer import (
    anonymize_text,
    neutralize_text,
    normalize_text,
    sanitize_project_text,
    truncate_text,
)


class ProjectSanitizerTests(SimpleTestCase):
    """Vérifie l'anonymisation et la neutralisation des textes."""

    def test_email_is_anonymized(self) -> None:
        """Une adresse e-mail est remplacée par son placeholder."""
        self.assertEqual(anonymize_text("Contact: user@example.com"), "Contact: [EMAIL]")

    def test_phone_is_anonymized(self) -> None:
        """Un numéro de téléphone est remplacé par son placeholder."""
        self.assertEqual(anonymize_text("Appelez le +33 6 12 34 56 78"), "Appelez le [TEL]")

    def test_link_is_anonymized(self) -> None:
        """Un lien HTTP ou www est remplacé par son placeholder."""
        self.assertEqual(anonymize_text("Voir https://example.com/path"), "Voir [LIEN]")
        self.assertEqual(anonymize_text("Voir www.example.com"), "Voir [LIEN]")

    def test_fullwidth_email_is_normalized_before_anonymization(self) -> None:
        """Un e-mail en pleine largeur est anonymisé après normalisation NFKC."""
        fullwidth_email = "ｕｓｅｒ＠ｅｘａｍｐｌｅ．ｃｏｍ"
        self.assertEqual(
            sanitize_project_text(fullwidth_email, 100),
            "[EMAIL]",
        )

    def test_truncation_does_not_split_placeholder(self) -> None:
        """La coupe se fait avant un placeholder qui dépasserait la limite."""
        text = "x" * 8 + "[EMAIL]" + "suffixe"
        result = truncate_text(text, 10)
        self.assertEqual(result, "x" * 8)
        self.assertNotIn("[EM", result)

    def test_project_closing_tag_is_neutralized(self) -> None:
        """Une balise de fin ASCII ne reste pas interprétable comme une balise."""
        self.assertEqual(
            sanitize_project_text("</projet>", 100),
            "‹/projet›",
        )

    def test_fullwidth_project_closing_tag_is_neutralized(self) -> None:
        """La NFKC convertit puis neutralise aussi les chevrons pleine largeur."""
        self.assertEqual(
            sanitize_project_text("＜/projet＞", 100),
            "‹/projet›",
        )

    def test_normal_text_is_unchanged(self) -> None:
        """Un texte sans donnée sensible reste identique."""
        text = "Décrire le projet et ses objectifs."
        self.assertEqual(sanitize_project_text(text, 100), text)

    def test_neutralize_only_replaces_angle_brackets(self) -> None:
        """La neutralisation ne modifie aucun autre caractère."""
        text = "a & b [EMAIL] déjà traité"
        self.assertEqual(neutralize_text(text), text)
        self.assertEqual(normalize_text(text), text)
