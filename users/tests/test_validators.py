"""Tests de validation des réponses de modération IA."""

from django.test import SimpleTestCase

from users.ai.exceptions import LLMResponseError
from users.ai.validators import parse_moderation_response


class ModerationResponseValidatorTests(SimpleTestCase):
    """Vérifie le parsing et la validation des réponses de modération."""

    def assert_invalid(self, raw_response):
        """Vérifie qu'une réponse invalide lève l'exception attendue."""
        with self.assertRaises(LLMResponseError):
            parse_moderation_response(raw_response)

    def test_valid_response(self):
        """Accepte une réponse JSON conforme et normalise ses valeurs."""
        result = parse_moderation_response(
            '{"statut": " OK ", "raison": " Profil cohérent. ", "confiance": 0.9}'
        )

        self.assertEqual(result, {
            "statut": "OK",
            "raison": "Profil cohérent.",
            "confiance": 0.9,
            "criteres": [],
        })

    def test_invalid_json(self):
        """Rejette une réponse qui n'est pas du JSON."""
        self.assert_invalid("pas du json")

    def test_empty_reason(self):
        """Rejette une raison vide ou composée d'espaces."""
        self.assert_invalid('{"statut": "OK", "raison": " ", "confiance": 0.5}')

    def test_missing_key(self):
        """Rejette une réponse à laquelle il manque une clé obligatoire."""
        self.assert_invalid('{"statut": "OK", "raison": "Doute."}')

    def test_non_text_status(self):
        """Rejette un statut qui n'est pas textuel."""
        self.assert_invalid('{"statut": 1, "raison": "Doute.", "confiance": 0.5}')

    def test_unknown_status(self):
        """Rejette un statut qui ne fait pas partie des catégories prévues."""
        self.assert_invalid(
            '{"statut": "INCONNU", "raison": "Doute.", "confiance": 0.5}'
        )

    def test_confidence_out_of_range(self):
        """Rejette une confiance située hors de l'intervalle [0, 1]."""
        self.assert_invalid(
            '{"statut": "SUSPECT", "raison": "Doute.", "confiance": 1.2}'
        )

    def test_boolean_confidence(self):
        """Rejette une valeur booléenne utilisée comme confiance."""
        self.assert_invalid(
            '{"statut": "OK", "raison": "Doute.", "confiance": true}'
        )

    def test_text_confidence(self):
        """Rejette une confiance textuelle."""
        self.assert_invalid(
            '{"statut": "OK", "raison": "Doute.", "confiance": "0.5"}'
        )

    def test_nan_confidence(self):
        """Rejette une confiance NaN."""
        self.assert_invalid(
            '{"statut": "OK", "raison": "Doute.", "confiance": NaN}'
        )

    def test_huge_integer_confidence(self):
        """Rejette un entier de confiance arbitrairement grand."""
        self.assert_invalid(
            '{"statut": "OK", "raison": "Doute.", "confiance": '
            + "9" * 10000
            + "}"
        )

    def test_json_list(self):
        """Rejette une réponse JSON qui est une liste."""
        self.assert_invalid('[{"statut": "OK"}]')

    def test_non_text_input(self):
        """Rejette une entrée qui n'est pas textuelle."""
        self.assert_invalid(None)

    def test_lowercase_status(self):
        """Accepte un statut en minuscules et le normalise."""
        result = parse_moderation_response(
            '{"statut": "suspect", "raison": "Doute.", "confiance": 0.5}'
        )

        self.assertEqual(result["statut"], "SUSPECT")

    def test_text_around_json(self):
        """Accepte du texte avant et après l'objet JSON."""
        result = parse_moderation_response(
            'Voici le résultat : {"statut": "OK", "raison": "Correct.", '
            '"confiance": 1} fin.'
        )

        self.assertEqual(result["statut"], "OK")

    def test_json_fence_with_language(self):
        """Accepte un objet entouré d'une clôture Markdown json."""
        result = parse_moderation_response(
            '```json\n{"statut": "REJETE", "raison": "Interdit.", '
            '"confiance": 0.8}\n```'
        )

        self.assertEqual(result["statut"], "REJETE")

    def test_json_fence_without_language(self):
        """Accepte un objet entouré d'une clôture Markdown sans langage."""
        result = parse_moderation_response(
            '```\n{"statut": "OK", "raison": "Correct.", "confiance": 0.7}\n```'
        )

        self.assertEqual(result["statut"], "OK")

    def test_extra_key_is_ignored(self):
        """Ignore les clés supplémentaires et renvoie les quatre clés prévues."""
        result = parse_moderation_response(
            '{"statut": "OK", "raison": "Correct.", "confiance": 0.7, '
            '"extra": "ignorée"}'
        )

        self.assertEqual(
            set(result),
            {"statut", "raison", "confiance", "criteres"},
        )

    def test_invalid_criteria_are_ignored(self):
        """Ignore les critères inconnus ou mal formés."""
        result = parse_moderation_response(
            '{"statut": "OK", "raison": "Correct.", "confiance": 0.7, '
            '"criteres": [{"id": "inconnu", "probleme": true, "commentaire": "x"}, '
            '{"id": "profil_trop_pauvre", "probleme": "oui", "commentaire": "x"}]}'
        )

        self.assertEqual(result["criteres"], [])

    def test_valid_criteria_are_kept_and_comments_are_truncated(self):
        """Conserve les critères valides et tronque leurs commentaires."""
        comment = "x" * 250
        result = parse_moderation_response(
            '{"statut": "OK", "raison": "Correct.", "confiance": 0.7, '
            f'"criteres": [{{"id": "profil_trop_pauvre", "probleme": true, '
            f'"commentaire": "{comment}"' + "}]}"
        )

        self.assertEqual(len(result["criteres"]), 1)
        self.assertEqual(len(result["criteres"][0]["commentaire"]), 200)
