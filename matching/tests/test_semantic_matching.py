"""Tests du matching sémantique, de sa validation et de son mode de repli."""

import json
from unittest.mock import patch

from django.test import TestCase, override_settings

from projects.ai.exceptions import LLMResponseError, LLMTimeoutError
from matching.services import semantic_matching
from matching.services.validators import parse_semantic_response

from .factories import ANALYSIS_RESULT, make_analysis, make_freelancer, make_owner, make_project

VALID_PAYLOAD = {
    "score_semantique": 82.5,
    "concepts_correspondants": ["API web", "Python"],
    "competences_pertinentes": ["Django"],
    "justification": "Le profil couvre le socle back-end demandé.",
}


class ValidatorTests(TestCase):
    """Validation stricte du JSON retourné par le LLM."""

    def test_valid_payload_is_accepted(self):
        """Une réponse conforme est normalisée sans perte."""
        result = parse_semantic_response(json.dumps(VALID_PAYLOAD))
        self.assertEqual(result["score_semantique"], 82.5)
        self.assertEqual(result["competences_pertinentes"], ["Django"])

    def test_optional_lists_default_to_empty(self):
        """Les listes facultatives absentes deviennent des listes vides."""
        payload = {
            "score_semantique": 10,
            "justification": "Peu de recouvrement.",
        }
        result = parse_semantic_response(json.dumps(payload))
        self.assertEqual(result["concepts_correspondants"], [])

    def test_non_json_is_rejected(self):
        """Un texte non JSON est rejeté."""
        with self.assertRaises(LLMResponseError):
            parse_semantic_response("pas du json")

    def test_empty_response_is_rejected(self):
        """Une réponse vide est rejetée."""
        with self.assertRaises(LLMResponseError):
            parse_semantic_response("")

    def test_unknown_field_is_rejected(self):
        """Un champ hors schéma est rejeté."""
        payload = dict(VALID_PAYLOAD, autorisation="admin")
        with self.assertRaises(LLMResponseError):
            parse_semantic_response(json.dumps(payload))

    def test_missing_required_field_is_rejected(self):
        """Une justification absente est rejetée."""
        payload = {"score_semantique": 50}
        with self.assertRaises(LLMResponseError):
            parse_semantic_response(json.dumps(payload))

    def test_score_out_of_range_is_rejected(self):
        """Un score hors de l'intervalle 0-100 est rejeté."""
        for value in (-1, 101):
            with self.subTest(value=value):
                payload = dict(VALID_PAYLOAD, score_semantique=value)
                with self.assertRaises(LLMResponseError):
                    parse_semantic_response(json.dumps(payload))

    def test_non_numeric_score_is_rejected(self):
        """Un score non numérique est rejeté."""
        payload = dict(VALID_PAYLOAD, score_semantique="80")
        with self.assertRaises(LLMResponseError):
            parse_semantic_response(json.dumps(payload))

    def test_boolean_score_is_rejected(self):
        """Un booléen n'est pas accepté comme score."""
        payload = dict(VALID_PAYLOAD, score_semantique=True)
        with self.assertRaises(LLMResponseError):
            parse_semantic_response(json.dumps(payload))

    def test_oversized_list_is_rejected(self):
        """Une liste trop longue est rejetée."""
        payload = dict(VALID_PAYLOAD, concepts_correspondants=[f"c{i}" for i in range(13)])
        with self.assertRaises(LLMResponseError):
            parse_semantic_response(json.dumps(payload))

    def test_non_dict_payload_is_rejected(self):
        """Une liste JSON au lieu d'un objet est rejetée."""
        with self.assertRaises(LLMResponseError):
            parse_semantic_response("[1, 2]")


class BlendTests(TestCase):
    """Formule d'intégration du score sémantique."""

    @override_settings(MATCHING_SEMANTIC_WEIGHT=0.25)
    def test_hybrid_formula_is_documented_and_applied(self):
        """Le score final applique la pondération configurée."""
        blended = semantic_matching.blend(
            60.0, {"available": True, "score": 100.0}
        )
        self.assertEqual(blended["mode"], "HYBRID")
        self.assertEqual(blended["total"], 70.0)

    def test_unavailable_semantic_falls_back_to_deterministic(self):
        """Sans signal sémantique, le score déterministe est conservé."""
        blended = semantic_matching.blend(
            64.0, {"available": False, "score": None}
        )
        self.assertEqual(blended["mode"], "DETERMINISTIC")
        self.assertEqual(blended["total"], 64.0)
        self.assertEqual(blended["semantic_weight"], 0.0)

    @override_settings(MATCHING_SEMANTIC_WEIGHT=5)
    def test_weight_is_clamped(self):
        """Un poids hors bornes est ramené dans l'intervalle 0-1."""
        self.assertEqual(semantic_matching.get_semantic_weight(), 1.0)


class EvaluateTests(TestCase):
    """Comportement du service face aux pannes du fournisseur."""

    def setUp(self):
        """Prépare un projet analysé et un freelance."""
        self.owner = make_owner()
        self.project = make_project(self.owner)
        make_analysis(self.project)
        self.freelancer = make_freelancer("semantic")

    def test_valid_llm_response_is_used(self):
        """Une réponse valide alimente le score sémantique."""
        with patch(
            "matching.services.semantic_matching.call_llm",
            return_value=json.dumps(VALID_PAYLOAD),
        ):
            result = semantic_matching.evaluate(
                self.project, ANALYSIS_RESULT, self.freelancer
            )
        self.assertTrue(result["available"])
        self.assertEqual(result["score"], 82.5)

    def test_timeout_does_not_raise(self):
        """Un dépassement de délai bascule en mode indisponible."""
        with patch(
            "matching.services.semantic_matching.call_llm",
            side_effect=LLMTimeoutError("timeout"),
        ):
            result = semantic_matching.evaluate(
                self.project, ANALYSIS_RESULT, self.freelancer
            )
        self.assertFalse(result["available"])
        self.assertEqual(result["reason"], "llm_indisponible")

    def test_invalid_json_does_not_raise(self):
        """Une réponse invalide est neutralisée sans faire échouer l'API."""
        with patch(
            "matching.services.semantic_matching.call_llm",
            return_value="{]",
        ):
            result = semantic_matching.evaluate(
                self.project, ANALYSIS_RESULT, self.freelancer
            )
        self.assertFalse(result["available"])

    def test_unexpected_error_is_contained(self):
        """Une erreur inattendue reste contenue dans le service."""
        with patch(
            "matching.services.semantic_matching.call_llm",
            side_effect=RuntimeError("boom"),
        ):
            result = semantic_matching.evaluate(
                self.project, ANALYSIS_RESULT, self.freelancer
            )
        self.assertFalse(result["available"])
        self.assertEqual(result["reason"], "erreur_interne")

    def test_prompt_contains_no_private_contact_data(self):
        """Les coordonnées présentes dans un texte sont neutralisées."""
        self.freelancer.bio = "Contactez-moi sur test@exemple.fr ou 0612345678."
        text = semantic_matching.build_user_text(
            self.project, ANALYSIS_RESULT, self.freelancer
        )
        self.assertNotIn("test@exemple.fr", text)
        self.assertNotIn("0612345678", text)
