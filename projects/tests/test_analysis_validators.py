"""Tests du parseur des analyses de projets."""

import copy
import json

from django.test import SimpleTestCase

from projects.ai.exceptions import LLMResponseError
from projects.ai.validators import parse_analysis_response


def valid_analysis() -> dict:
    """Retourne une analyse complète et valide."""
    return {
        "budget_min": 1000,
        "budget_max": 2500,
        "devise": "EUR",
        "nb_freelancers": 2,
        "specialites": [{"nom": "Backend Django", "nb": 1}],
        "duree_semaines": 8,
        "complexite": "MOYENNE",
        "risques": ["La description manque de détails techniques."],
        "jalons": ["Cadrage", "Développement"],
        "coherence_budget": "COHERENT",
        "recommandation": "Préciser les besoins avant le lancement.",
        "confiance": 0.8,
    }


class AnalysisValidatorTests(SimpleTestCase):
    """Vérifie les réponses valides, invalides et malicieuses."""

    def assert_invalid(self, value) -> None:
        """Vérifie qu'une entrée invalide lève l'exception locale."""
        with self.assertRaises(LLMResponseError):
            parse_analysis_response(value)

    def test_valid_response_returns_exactly_the_twelve_fields(self) -> None:
        """Les clés supplémentaires sont ignorées."""
        analysis = valid_analysis()
        analysis["extra"] = "ignoré"

        result = parse_analysis_response(json.dumps(analysis))

        self.assertEqual(set(result), set(valid_analysis()))
        self.assertNotIn("extra", result)

    def test_json_invalid(self) -> None:
        """Un texte qui n'est pas du JSON est rejeté."""
        self.assert_invalid("{not-json")

    def test_boundary_values_are_accepted(self) -> None:
        """Les bornes inclusives demandées sont acceptées."""
        analysis = valid_analysis()
        analysis["nb_freelancers"] = 50
        analysis["duree_semaines"] = 520
        analysis["confiance"] = 1
        analysis["specialites"][0]["nb"] = 50
        self.assertIsInstance(parse_analysis_response(json.dumps(analysis)), dict)

        analysis = valid_analysis()
        analysis["nb_freelancers"] = 1
        analysis["duree_semaines"] = 1
        analysis["confiance"] = 0
        self.assertIsInstance(parse_analysis_response(json.dumps(analysis)), dict)

    def test_out_of_bounds_values_are_rejected(self) -> None:
        """Les effectifs, durées et confiances hors bornes sont rejetés."""
        for field, value in (
            ("nb_freelancers", 0),
            ("nb_freelancers", 51),
            ("duree_semaines", 0),
            ("duree_semaines", 521),
            ("confiance", -0.01),
            ("confiance", 1.01),
        ):
            analysis = valid_analysis()
            analysis[field] = value
            self.assert_invalid(json.dumps(analysis))

    def test_budget_min_greater_than_max_is_rejected(self) -> None:
        """Un budget minimum supérieur au maximum est rejeté."""
        analysis = valid_analysis()
        analysis["budget_min"] = 3000
        self.assert_invalid(json.dumps(analysis))

    def test_boolean_is_not_accepted_as_number(self) -> None:
        """Un booléen ne peut pas être utilisé comme un nombre."""
        analysis = valid_analysis()
        analysis["confiance"] = True
        self.assert_invalid(json.dumps(analysis))

    def test_non_finite_numbers_are_rejected(self) -> None:
        """Infinity et les exposants qui produisent l'infini sont rejetés."""
        analysis = valid_analysis()
        self.assert_invalid(json.dumps(analysis).replace("2500", "Infinity"))
        self.assert_invalid(json.dumps(analysis).replace("2500", "1e999"))

    def test_huge_integer_is_rejected_without_raw_error(self) -> None:
        """Un entier gigantesque ne provoque pas d'erreur Python brute."""
        analysis = valid_analysis()
        raw = json.dumps(analysis).replace("2500", "9" * 5000)
        self.assert_invalid(raw)

    def test_json_root_must_be_an_object(self) -> None:
        """Les racines tableau, nombre et null sont rejetées."""
        for raw in ("[]", "42", "null"):
            self.assert_invalid(raw)

    def test_two_json_objects_are_rejected(self) -> None:
        """Deux objets JSON dans une même réponse sont ambigus et rejetés."""
        raw = f"{json.dumps(valid_analysis())}\n{json.dumps(valid_analysis())}"
        self.assert_invalid(raw)

    def test_json_fence_and_surrounding_text_are_tolerated(self) -> None:
        """Un objet entouré de texte et d'une clôture Markdown est extrait."""
        raw = "Résultat :\n```json\n" + json.dumps(valid_analysis()) + "\n```"
        self.assertIsInstance(parse_analysis_response(raw), dict)

    def test_status_values_are_normalized(self) -> None:
        """Les énumérations acceptent la casse et les espaces périphériques."""
        analysis = valid_analysis()
        analysis["complexite"] = "  faible "
        analysis["coherence_budget"] = " sous_estime "

        result = parse_analysis_response(json.dumps(analysis))

        self.assertEqual(result["complexite"], "FAIBLE")
        self.assertEqual(result["coherence_budget"], "SOUS_ESTIME")

    def test_string_items_are_stripped_before_empty_check(self) -> None:
        """Les espaces périphériques sont retirés des éléments textuels."""
        analysis = valid_analysis()
        analysis["risques"] = ["  Risque détaillé  "]
        analysis["jalons"] = ["  Cadrage  ", " Développement "]
        analysis["specialites"] = [{"nom": "  Backend  ", "nb": 1}]

        result = parse_analysis_response(json.dumps(analysis))

        self.assertEqual(result["risques"], ["Risque détaillé"])
        self.assertEqual(result["jalons"], ["Cadrage", "Développement"])
        self.assertEqual(result["specialites"][0]["nom"], "Backend")

    def test_empty_string_items_are_rejected(self) -> None:
        """Un élément vide après strip est rejeté."""
        for field in ("risques", "jalons"):
            analysis = valid_analysis()
            analysis[field] = ["   "] if field == "risques" else ["   ", "Jalon"]
            self.assert_invalid(json.dumps(analysis))

    def test_input_is_not_mutated(self) -> None:
        """Le parseur ne modifie pas le dictionnaire fourni au sérialiseur JSON."""
        analysis = valid_analysis()
        original = copy.deepcopy(analysis)
        parse_analysis_response(json.dumps(analysis))
        self.assertEqual(analysis, original)
