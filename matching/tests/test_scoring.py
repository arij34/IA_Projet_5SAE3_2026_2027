"""Tests du moteur de scoring déterministe."""

from django.test import TestCase, override_settings

from matching.constants import DEFAULT_WEIGHTS
from matching.services import scoring
from matching.services.quiz_scoring import load_quiz_profile, speciality_quiz_score

from .factories import ANALYSIS_RESULT, make_freelancer, make_quiz_attempt

PYTHON_SPECIALITY = ANALYSIS_RESULT["specialites"][0]


class SkillsSubscoreTests(TestCase):
    """Sous-score de couverture des compétences."""

    def test_full_coverage_scores_maximum(self):
        """Une compétence identique à la spécialité donne 100."""
        result = scoring.skills_subscore(PYTHON_SPECIALITY, ["Python", "Django"])
        self.assertTrue(result["available"])
        self.assertEqual(result["score"], 100.0)
        self.assertEqual(result["missing"], [])

    def test_missing_skill_scores_zero_and_lists_gap(self):
        """Une spécialité non couverte est signalée comme manquante."""
        result = scoring.skills_subscore(PYTHON_SPECIALITY, ["Comptabilité"])
        self.assertEqual(result["score"], 0.0)
        self.assertEqual(result["missing"], ["python"])

    def test_empty_skills_scores_zero(self):
        """Un freelance sans compétence déclarée obtient zéro, pas une erreur."""
        result = scoring.skills_subscore(PYTHON_SPECIALITY, [])
        self.assertTrue(result["available"])
        self.assertEqual(result["score"], 0.0)

    def test_synonym_is_recognized(self):
        """Un synonyme déclaré est reconnu comme la compétence requise."""
        speciality = {"nom": "JavaScript", "nb": 1, "niveau": "JUNIOR",
                      "charge_pourcentage": 100.0}
        result = scoring.skills_subscore(speciality, ["JS"])
        self.assertEqual(result["score"], 100.0)

    def test_hyphen_does_not_create_a_parasite_token(self):
        """« e-commerce » ne produit pas de jeton parasite « e »."""
        speciality = {"nom": "Développement e-commerce", "nb": 1,
                      "niveau": "CONFIRME", "charge_pourcentage": 100.0}
        result = scoring.skills_subscore(speciality, ["E-commerce"])
        self.assertEqual(result["score"], 100.0)
        self.assertEqual(result["missing"], [])

    def test_single_letter_languages_are_preserved(self):
        """Les langages d'une seule lettre restent exploitables."""
        speciality = {"nom": "C", "nb": 1, "niveau": "CONFIRME",
                      "charge_pourcentage": 100.0}
        self.assertEqual(scoring.skills_subscore(speciality, ["C"])["score"], 100.0)
        self.assertEqual(scoring.skills_subscore(speciality, ["Python"])["score"], 0.0)


class BudgetSubscoreTests(TestCase):
    """Sous-score de compatibilité budgétaire."""

    def test_affordable_rate_uses_charge_and_headcount(self):
        """Le tarif finançable découle du budget, de la charge et de la durée."""
        rate = scoring.affordable_hourly_rate(ANALYSIS_RESULT, PYTHON_SPECIALITY)
        # 10000 * 0.60 / 1 poste / (10 semaines * 35 h * 0.5) = 34.29
        self.assertAlmostEqual(rate, 34.2857, places=3)

    def test_rate_within_budget_scores_maximum(self):
        """Un tarif inférieur au tarif finançable obtient 100."""
        result = scoring.budget_subscore(ANALYSIS_RESULT, PYTHON_SPECIALITY, 30)
        self.assertEqual(result["score"], 100.0)

    def test_rate_above_budget_decreases_score(self):
        """Un dépassement réduit le score sans le rendre négatif."""
        result = scoring.budget_subscore(ANALYSIS_RESULT, PYTHON_SPECIALITY, 40)
        self.assertTrue(0 < result["score"] < 100)

    def test_rate_far_above_budget_scores_zero(self):
        """Au-delà de la tolérance, le sous-score budget tombe à zéro."""
        result = scoring.budget_subscore(ANALYSIS_RESULT, PYTHON_SPECIALITY, 300)
        self.assertEqual(result["score"], 0.0)

    def test_missing_rate_disables_criterion(self):
        """Un tarif absent neutralise le critère au lieu de pénaliser."""
        result = scoring.budget_subscore(ANALYSIS_RESULT, PYTHON_SPECIALITY, None)
        self.assertFalse(result["available"])
        self.assertIsNone(result["score"])

    def test_missing_duration_disables_criterion(self):
        """Une analyse sans durée neutralise le critère budget."""
        analysis = dict(ANALYSIS_RESULT)
        analysis.pop("duree_semaines")
        result = scoring.budget_subscore(analysis, PYTHON_SPECIALITY, 40)
        self.assertFalse(result["available"])


class LevelSubscoreTests(TestCase):
    """Sous-score de niveau et inférence du niveau du freelance."""

    def test_level_inferred_from_quiz_average(self):
        """La moyenne de quiz prime sur le tarif pour estimer le niveau."""
        estimated = scoring.estimate_level(10, {"global_average": 90.0})
        self.assertEqual(estimated, {"level": "SENIOR", "source": "quiz"})

    def test_level_inferred_from_rate_when_no_quiz(self):
        """Sans quiz, le tarif sert de signal de niveau."""
        estimated = scoring.estimate_level(80, {})
        self.assertEqual(estimated, {"level": "SENIOR", "source": "tarif"})

    def test_level_unavailable_without_any_signal(self):
        """Sans quiz ni tarif, le niveau reste inconnu."""
        estimated = scoring.estimate_level(None, {})
        self.assertIsNone(estimated["level"])

    def test_exact_level_match_scores_maximum(self):
        """Un niveau estimé identique au niveau requis donne 100."""
        result = scoring.level_subscore(PYTHON_SPECIALITY, 50, {"global_average": 60.0})
        self.assertEqual(result["estimated_level"], "CONFIRME")
        self.assertEqual(result["score"], 100.0)

    def test_underqualified_scores_less_than_overqualified(self):
        """Être sous-qualifié pénalise davantage qu'être sur-qualifié."""
        under = scoring.level_subscore(
            PYTHON_SPECIALITY, None, {"global_average": 30.0}
        )
        over = scoring.level_subscore(
            PYTHON_SPECIALITY, None, {"global_average": 90.0}
        )
        self.assertLess(under["score"], over["score"])

    def test_unknown_level_disables_criterion(self):
        """Un niveau inestimable neutralise le critère."""
        result = scoring.level_subscore(PYTHON_SPECIALITY, None, {})
        self.assertFalse(result["available"])


class QuizSubscoreTests(TestCase):
    """Sous-score de compétence démontrée par les quiz."""

    def test_no_attempt_disables_criterion_instead_of_zero(self):
        """Un freelance sans quiz n'est jamais noté zéro sur ce critère."""
        result = speciality_quiz_score({"by_category": {}}, ["Python"])
        self.assertFalse(result["available"])
        self.assertIsNone(result["score"])

    def test_matching_category_uses_its_average(self):
        """Un quiz de la catégorie demandée fournit directement le score."""
        user = make_freelancer("quizuser")
        make_quiz_attempt(user, "python", 80)
        profile = load_quiz_profile(user)
        result = speciality_quiz_score(profile, ["Python"])
        self.assertTrue(result["available"])
        self.assertEqual(result["source"], "specialite")
        self.assertEqual(result["score"], 80.0)

    def test_other_category_is_damped(self):
        """Un quiz hors spécialité est pris en compte mais atténué."""
        user = make_freelancer("quizuser2")
        make_quiz_attempt(user, "react", 100)
        profile = load_quiz_profile(user)
        result = speciality_quiz_score(profile, ["Python"], 0.8)
        self.assertEqual(result["source"], "indirect")
        self.assertEqual(result["score"], 80.0)


class AggregationTests(TestCase):
    """Agrégation pondérée et renormalisation."""

    def test_weights_are_renormalized_when_a_criterion_is_missing(self):
        """Les poids des critères disponibles sont renormalisés à 1."""
        subscores = {
            "skills": {"available": True, "score": 100.0},
            "budget": {"available": True, "score": 0.0},
            "level": {"available": False, "score": None},
            "quiz": {"available": False, "score": None},
        }
        result = scoring.aggregate(subscores, DEFAULT_WEIGHTS)
        self.assertEqual(
            sorted(result["applied_weights"]), ["budget", "skills"]
        )
        self.assertAlmostEqual(sum(result["applied_weights"].values()), 1.0, places=4)
        # 100 * (0.40 / 0.60) = 66.67
        self.assertAlmostEqual(result["score"], 66.67, places=2)
        self.assertEqual(result["skipped"], ["level", "quiz"])

    def test_no_available_criterion_returns_zero(self):
        """Sans aucun critère disponible, le score vaut zéro et le signale."""
        subscores = {"skills": {"available": False, "score": None}}
        result = scoring.aggregate(subscores, DEFAULT_WEIGHTS)
        self.assertEqual(result["score"], 0.0)
        self.assertEqual(result["applied_weights"], {})


class ScoreSpecialityTests(TestCase):
    """Score complet d'un freelance pour une spécialité."""

    def setUp(self):
        """Prépare un freelance de référence."""
        self.freelancer = make_freelancer("alice", skills=["Python", "Django"])

    def test_result_is_reproducible(self):
        """Deux calculs identiques produisent exactement le même score."""
        first = scoring.score_speciality(
            ANALYSIS_RESULT, PYTHON_SPECIALITY, self.freelancer, {}
        )
        second = scoring.score_speciality(
            ANALYSIS_RESULT, PYTHON_SPECIALITY, self.freelancer, {}
        )
        self.assertEqual(first["deterministic_score"], second["deterministic_score"])

    def test_explanations_are_produced_for_every_criterion(self):
        """Chaque critère produit une explication lisible."""
        result = scoring.score_speciality(
            ANALYSIS_RESULT, PYTHON_SPECIALITY, self.freelancer, {}
        )
        self.assertEqual(len(scoring.explain(result)), 4)

    def test_best_speciality_is_selected(self):
        """Le meilleur score parmi les spécialités du projet est retenu."""
        result = scoring.best_speciality_score(ANALYSIS_RESULT, self.freelancer, {})
        self.assertEqual(result["speciality"], "Python")
        self.assertEqual(len(result["all_specialities"]), 2)

    @override_settings(MATCHING_WEIGHTS={"skills": 1.0, "budget": 0.0,
                                         "level": 0.0, "quiz": 0.0})
    def test_weights_are_configurable(self):
        """Les poids se surchargent par les réglages Django."""
        weights = scoring.get_weights()
        self.assertEqual(weights["skills"], 1.0)
        result = scoring.score_speciality(
            ANALYSIS_RESULT, PYTHON_SPECIALITY, self.freelancer, {}, weights
        )
        self.assertEqual(result["deterministic_score"], 100.0)
