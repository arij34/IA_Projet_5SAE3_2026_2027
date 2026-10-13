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
        "budget_recommande": 1800,
        "devise": "EUR",
        "nb_freelancers": 2,
        "specialites": [
            {
                "nom": "Backend Django",
                "nb": 2,
                "niveau": "confirme",
                "charge_pourcentage": 100,
            }
        ],
        "duree_semaines": 8,
        "duree_min_semaines": 6,
        "duree_max_semaines": 10,
        "complexite": "MOYENNE",
        "score_complexite": 5,
        "facteurs_complexite": ["Intégration avec le système existant"],
        "risques": [
            {
                "description": "La description manque de détails techniques.",
                "probabilite": 0.4,
                "impact": "MOYEN",
                "mitigation": "Valider les interfaces en cadrage.",
            }
        ],
        "jalons": [{"nom": "Cadrage", "semaine": 2}, {"nom": "Recette", "semaine": 8}],
        "coherence_budget": "REALISTE",
        "recommandation": "Préciser les besoins avant le lancement.",
        "confiance": 0.8,
        "justification": "Le périmètre décrit nécessite une phase de cadrage.",
        "phases": [
            {
                "nom": "Cadrage",
                "objectif": "Préciser le besoin",
                "duree_semaines": 2,
                "livrables": ["Spécifications"],
                "specialites": ["Backend Django"],
                "budget_pourcentage": 25,
            },
            {
                "nom": "Développement",
                "objectif": "Construire la solution",
                "duree_semaines": 3,
                "livrables": ["Version initiale"],
                "specialites": ["Backend Django"],
                "budget_pourcentage": 40,
            },
            {
                "nom": "Recette",
                "objectif": "Valider la solution",
                "duree_semaines": 3,
                "livrables": ["Procès-verbal"],
                "specialites": ["Backend Django"],
                "budget_pourcentage": 35,
            },
        ],
        "faisabilite_deadline": "TENABLe",
        "faisabilite_deadline_justification": "La durée estimée tient dans le délai.",
        "taux_reussite": 0.75,
        "facteurs_positifs": ["Objectif identifié"],
        "facteurs_negatifs": ["Détails techniques incomplets"],
        "hypotheses": ["Les accès techniques seront disponibles."],
        "questions_clarification": ["Quels systèmes doivent être intégrés ?"],
        "recommandations": ["Valider les spécifications avec les parties prenantes."],
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

    def test_each_required_field_is_rejected_when_missing(self) -> None:
        """Chaque clé obligatoire est effectivement requise."""
        for field in valid_analysis():
            with self.subTest(field=field):
                analysis = valid_analysis()
                del analysis[field]
                self.assert_invalid(json.dumps(analysis))

    def test_json_invalid(self) -> None:
        """Un texte qui n'est pas du JSON est rejeté."""
        self.assert_invalid("{not-json")

    def test_unknown_complexity_is_rejected(self) -> None:
        """Une valeur de complexité inconnue est rejetée."""
        analysis = valid_analysis()
        analysis["complexite"] = "EXTREME"
        self.assert_invalid(json.dumps(analysis))

    def test_fifty_specialities_are_accepted_but_fifty_one_are_rejected(self) -> None:
        """La liste des spécialités respecte la borne maximale de 50 éléments."""
        analysis = valid_analysis()
        analysis["specialites"] = [
            {
                "nom": f"Spécialité {index}",
                "nb": 1,
                "niveau": "junior",
                "charge_pourcentage": 2,
            }
            for index in range(50)
        ]
        analysis["nb_freelancers"] = 50
        analysis["phases"] = [
            {**phase, "specialites": ["Spécialité 0"]}
            for phase in analysis["phases"]
        ]
        self.assertIsInstance(parse_analysis_response(json.dumps(analysis)), dict)

        analysis["specialites"].append(
            {
                "nom": "Spécialité 51",
                "nb": 1,
                "niveau": "junior",
                "charge_pourcentage": 0,
            }
        )
        self.assert_invalid(json.dumps(analysis))

    def test_five_hundred_character_item_is_accepted_but_five_hundred_one_is_rejected(
        self,
    ) -> None:
        """Les éléments textuels sont limités à 500 caractères."""
        analysis = valid_analysis()
        analysis["risques"][0]["description"] = "R" * 500
        self.assertIsInstance(parse_analysis_response(json.dumps(analysis)), dict)

        analysis["risques"][0]["description"] = "R" * 501
        self.assert_invalid(json.dumps(analysis))

    def test_speciality_requires_name_and_count(self) -> None:
        """Une spécialité doit contenir un nom et un effectif."""
        for speciality in ({"nb": 1}, {"nom": "Backend"}):
            with self.subTest(speciality=speciality):
                analysis = valid_analysis()
                analysis["specialites"] = [speciality]
                self.assert_invalid(json.dumps(analysis))

    def test_boundary_values_are_accepted(self) -> None:
        """Les bornes inclusives demandées sont acceptées."""
        analysis = valid_analysis()
        analysis["nb_freelancers"] = 50
        analysis["duree_semaines"] = 520
        analysis["confiance"] = 1
        analysis["specialites"][0]["nb"] = 50
        analysis["specialites"][0]["charge_pourcentage"] = 100
        analysis["duree_min_semaines"] = 1
        analysis["duree_max_semaines"] = 520
        analysis["phases"] = [
            {**phase, "duree_semaines": duration}
            for phase, duration in zip(analysis["phases"], (170, 170, 180))
        ]
        self.assertIsInstance(parse_analysis_response(json.dumps(analysis)), dict)

        analysis = valid_analysis()
        analysis["nb_freelancers"] = 1
        analysis["specialites"][0]["nb"] = 1
        analysis["duree_semaines"] = 3
        analysis["confiance"] = 0
        analysis["duree_min_semaines"] = 1
        analysis["duree_max_semaines"] = 3
        analysis["phases"] = [
            {**phase, "duree_semaines": 1, "budget_pourcentage": 100 / 3}
            for phase in analysis["phases"]
        ]
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

    def test_detailed_bounds_are_accepted_and_refused(self) -> None:
        """Les bornes détaillées acceptent leurs limites et refusent les écarts."""
        accepted = valid_analysis()
        accepted["score_complexite"] = 1
        accepted["duree_min_semaines"] = 1
        accepted["duree_semaines"] = 3
        accepted["duree_max_semaines"] = 520
        accepted["taux_reussite"] = 0
        accepted["specialites"][0]["charge_pourcentage"] = 100
        accepted["phases"] = [
            {**phase, "duree_semaines": 1, "budget_pourcentage": 100 / 3}
            for phase in accepted["phases"]
        ]
        self.assertIsInstance(parse_analysis_response(json.dumps(accepted)), dict)

        for field, value in (
            ("score_complexite", 0),
            ("score_complexite", 11),
            ("duree_min_semaines", 0),
            ("duree_max_semaines", 521),
            ("taux_reussite", -0.01),
            ("taux_reussite", 1.01),
        ):
            with self.subTest(field=field, value=value):
                invalid = valid_analysis()
                invalid[field] = value
                self.assert_invalid(json.dumps(invalid))

    def test_budget_recommended_must_be_between_bounds(self) -> None:
        """Le budget recommandé reste dans l'intervalle annoncé."""
        for value in (999, 2501):
            with self.subTest(value=value):
                analysis = valid_analysis()
                analysis["budget_recommande"] = value
                self.assert_invalid(json.dumps(analysis))

    def test_phase_count_and_percentage_sum_are_coherent(self) -> None:
        """Les phases sont bornées et leurs budgets totalisent 100 %."""
        analysis = valid_analysis()
        analysis["phases"][0]["budget_pourcentage"] = 50
        self.assert_invalid(json.dumps(analysis))

        analysis = valid_analysis()
        analysis["phases"] = analysis["phases"][:2]
        self.assert_invalid(json.dumps(analysis))

    def test_phase_durations_specialities_and_team_sum_are_coherent(self) -> None:
        """Les phases doivent respecter durée, spécialités et équipe."""
        analysis = valid_analysis()
        analysis["phases"][0]["duree_semaines"] = 0
        self.assert_invalid(json.dumps(analysis))

        analysis = valid_analysis()
        analysis["phases"][0]["specialites"] = ["Inconnue"]
        self.assert_invalid(json.dumps(analysis))

        analysis = valid_analysis()
        analysis["nb_freelancers"] = 1
        self.assert_invalid(json.dumps(analysis))

    def test_structured_booleans_are_rejected(self) -> None:
        """Les booléens ne remplacent aucun nombre structuré."""
        for path in (
            ("score_complexite",),
            ("budget_recommande",),
            ("taux_reussite",),
            ("specialites", 0, "charge_pourcentage"),
            ("risques", 0, "probabilite"),
            ("phases", 0, "budget_pourcentage"),
        ):
            with self.subTest(path=path):
                analysis = valid_analysis()
                target = analysis
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = True
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
        analysis["coherence_budget"] = " realiste "

        result = parse_analysis_response(json.dumps(analysis))

        self.assertEqual(result["complexite"], "FAIBLE")
        self.assertEqual(result["coherence_budget"], "REALISTE")

    def test_string_items_are_stripped_before_empty_check(self) -> None:
        """Les espaces périphériques sont retirés des éléments textuels."""
        analysis = valid_analysis()
        analysis["risques"][0]["description"] = "  Risque détaillé  "
        analysis["jalons"] = [
            {"nom": "  Cadrage  ", "semaine": 2},
            {"nom": " Développement ", "semaine": 8},
        ]
        analysis["specialites"] = [
            {
                "nom": "  Backend  ",
                "nb": 2,
                "niveau": "confirme",
                "charge_pourcentage": 100,
            }
        ]
        analysis["phases"] = [
            {**phase, "specialites": ["  Backend  "]} for phase in analysis["phases"]
        ]

        result = parse_analysis_response(json.dumps(analysis))

        self.assertEqual(result["risques"][0]["description"], "Risque détaillé")
        self.assertEqual(result["jalons"][0]["nom"], "Cadrage")
        self.assertEqual(result["specialites"][0]["nom"], "Backend")

    def test_empty_string_items_are_rejected(self) -> None:
        """Un élément vide après strip est rejeté."""
        for field in ("risques", "jalons"):
            analysis = valid_analysis()
            if field == "risques":
                analysis[field][0]["description"] = "   "
            else:
                analysis[field][0]["nom"] = "   "
            self.assert_invalid(json.dumps(analysis))

    def test_input_is_not_mutated(self) -> None:
        """Le parseur ne modifie pas le dictionnaire fourni au sérialiseur JSON."""
        analysis = valid_analysis()
        original = copy.deepcopy(analysis)
        parse_analysis_response(json.dumps(analysis))
        self.assertEqual(analysis, original)

    def test_error_does_not_include_raw_response(self) -> None:
        """Le message d'erreur ne révèle aucun extrait de la réponse brute."""
        raw = '{"complexite":"INCONNUE","secret":"contenu-confidentiel"}'

        with self.assertRaises(LLMResponseError) as context:
            parse_analysis_response(raw)

        self.assertNotIn("INCONNUE", str(context.exception))
        self.assertNotIn("contenu-confidentiel", str(context.exception))
