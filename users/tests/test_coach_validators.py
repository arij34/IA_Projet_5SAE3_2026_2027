"""Tests de validation des réponses du coach de profil IA."""

from django.test import SimpleTestCase

from users.ai.coach_validators import parse_coach_response
from users.ai.exceptions import LLMResponseError


class CoachResponseValidatorTests(SimpleTestCase):
    """Vérifie le parsing et la validation des réponses du coach."""

    def assert_invalid(self, raw_response):
        """Vérifie qu'une réponse invalide lève l'exception attendue."""
        with self.assertRaises(LLMResponseError):
            parse_coach_response(raw_response)

    def valid_response(self):
        """Retourne une réponse JSON valide minimale."""
        return (
            '{"score": 84.6, "points_forts": ["Expertise"], '
            '"points_faibles": [], "suggestions": ["Ajouter un portfolio"]}'
        )

    def test_valid_response(self):
        """Accepte et normalise une réponse JSON conforme."""
        self.assertEqual(
            parse_coach_response(self.valid_response()),
            {
                "score": 85,
                "points_forts": ["Expertise"],
                "points_faibles": [],
                "suggestions": ["Ajouter un portfolio"],
            },
        )

    def test_score_boundary_values(self):
        """Accepte les scores aux bornes de l'intervalle."""
        for score in (0, 100):
            result = parse_coach_response(
                f'{{"score": {score}, "points_forts": [], '
                '"points_faibles": [], "suggestions": ["x"]}'
            )
            self.assertEqual(result["score"], score)
            self.assertIsInstance(result["score"], int)

    def test_score_half_uses_python_rounding(self):
        """Utilise l'arrondi Python actuel pour un score égal à 84,5."""
        # round(84.5) applique l'arrondi bancaire de Python et renvoie 84.
        result = parse_coach_response(
            '{"score": 84.5, "points_forts": [], "points_faibles": [], '
            '"suggestions": ["x"]}'
        )
        self.assertEqual(result["score"], 84)

    def test_json_fence_with_language(self):
        """Accepte une réponse entourée d'une clôture Markdown json."""
        result = parse_coach_response(f"```json\n{self.valid_response()}\n```")
        self.assertEqual(result["score"], 85)

    def test_text_around_json(self):
        """Accepte du texte avant et après l'objet JSON."""
        result = parse_coach_response(
            f"Voici l'analyse : {self.valid_response()} Fin de l'analyse."
        )
        self.assertEqual(result["suggestions"], ["Ajouter un portfolio"])

    def test_extra_keys_are_ignored(self):
        """Ignore les clés supplémentaires et renvoie exactement quatre clés."""
        result = parse_coach_response(
            '{"score": 50, "points_forts": [], "points_faibles": [], '
            '"suggestions": ["x"], "extra": "ignorée"}'
        )
        self.assertEqual(
            set(result),
            {"score", "points_forts", "points_faibles", "suggestions"},
        )

    def test_invalid_json(self):
        """Rejette une réponse qui n'est pas du JSON."""
        self.assert_invalid("pas du json")

    def test_missing_key(self):
        """Rejette une réponse à laquelle il manque une clé obligatoire."""
        self.assert_invalid(
            '{"score": 50, "points_forts": [], "points_faibles": []}'
        )

    def test_score_out_of_range(self):
        """Rejette les scores inférieurs à zéro ou supérieurs à cent."""
        for score in (-1, 101):
            self.assert_invalid(
                f'{{"score": {score}, "points_forts": [], '
                '"points_faibles": [], "suggestions": ["x"]}'
            )

    def test_boolean_score(self):
        """Rejette un booléen utilisé comme score."""
        self.assert_invalid(
            '{"score": true, "points_forts": [], "points_faibles": [], '
            '"suggestions": ["x"]}'
        )

    def test_string_score(self):
        """Rejette un score textuel."""
        self.assert_invalid(
            '{"score": "50", "points_forts": [], "points_faibles": [], '
            '"suggestions": ["x"]}'
        )

    def test_nan_score(self):
        """Rejette un score NaN."""
        self.assert_invalid(
            '{"score": NaN, "points_forts": [], "points_faibles": [], '
            '"suggestions": ["x"]}'
        )

    def test_infinite_scores(self):
        """Rejette les scores infinis explicites ou issus d'un débordement."""
        for score in ("Infinity", "1e999"):
            self.assert_invalid(
                f'{{"score": {score}, "points_forts": [], '
                '"points_faibles": [], "suggestions": ["x"]}'
            )

    def test_huge_integer_score(self):
        """Rejette un entier de score arbitrairement grand."""
        self.assert_invalid(
            '{"score": ' + "9" * 10000 + ', "points_forts": [], '
            '"points_faibles": [], "suggestions": ["x"]}'
        )

    def test_non_object_json_values(self):
        """Rejette les réponses JSON qui ne sont pas des objets."""
        for raw_response in ("[]", "42", '"texte"', "null"):
            self.assert_invalid(raw_response)

    def test_non_list_field(self):
        """Rejette un champ de points qui n'est pas une liste."""
        self.assert_invalid(
            '{"score": 50, "points_forts": "expertise", '
            '"points_faibles": [], "suggestions": ["x"]}'
        )

    def test_non_string_item(self):
        """Rejette un élément de liste qui n'est pas une chaîne."""
        self.assert_invalid(
            '{"score": 50, "points_forts": [1], "points_faibles": [], '
            '"suggestions": ["x"]}'
        )

    def test_empty_item(self):
        """Rejette un élément vide ou composé uniquement d'espaces."""
        self.assert_invalid(
            '{"score": 50, "points_forts": ["   "], "points_faibles": [], '
            '"suggestions": ["x"]}'
        )

    def test_item_is_stripped(self):
        """Supprime les espaces autour d'un élément textuel."""
        result = parse_coach_response(
            '{"score": 50, "points_forts": [], "points_faibles": [], '
            '"suggestions": [" Ajouter un portfolio "]}'
        )
        self.assertEqual(result["suggestions"], ["Ajouter un portfolio"])

    def test_empty_suggestions(self):
        """Rejette une liste de suggestions vide."""
        self.assert_invalid(
            '{"score": 50, "points_forts": [], "points_faibles": [], '
            '"suggestions": []}'
        )

    def test_more_than_five_items_keeps_first_five(self):
        """Conserve uniquement les cinq premiers éléments d'une liste."""
        response = (
            '{"score": 50, "points_forts": [], "points_faibles": [], '
            '"suggestions": ["1", "2", "3", "4", "5", "6"]}'
        )
        self.assertEqual(
            parse_coach_response(response)["suggestions"],
            ["1", "2", "3", "4", "5"],
        )

    def test_more_than_five_strengths_keeps_first_five(self):
        """Conserve les cinq premiers points forts."""
        response = (
            '{"score": 50, "points_forts": ["1", "2", "3", "4", "5", "6"], '
            '"points_faibles": [], "suggestions": ["x"]}'
        )
        self.assertEqual(
            parse_coach_response(response)["points_forts"],
            ["1", "2", "3", "4", "5"],
        )

    def test_long_item_is_truncated(self):
        """Tronque un élément à la longueur maximale autorisée."""
        item = "x" * 201
        response = (
            '{"score": 50, "points_forts": [], "points_faibles": [], '
            f'"suggestions": ["{item}"]}}'
        )
        self.assertEqual(len(parse_coach_response(response)["suggestions"][0]), 200)
