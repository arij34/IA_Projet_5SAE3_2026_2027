"""Tests de la composition automatique d'équipe."""

import copy

from django.test import TestCase, override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from matching.services.team_builder import build_team
from users.models import User

from .factories import (
    ANALYSIS_RESULT,
    make_analysis,
    make_freelancer,
    make_owner,
    make_project,
)

# Analyse à une seule spécialité, calquée sur le cas « test projet » observé :
# un poste de développement mobile, 7 semaines, budget de 2 500 euros.
MOBILE_ANALYSIS = {
    "budget_min": 1900,
    "budget_max": 3400,
    "budget_recommande": 2500,
    "devise": "EUR",
    "nb_freelancers": 1,
    "duree_semaines": 7,
    "complexite": "MOYENNE",
    "specialites": [
        {
            "nom": "Développement mobile",
            "nb": 1,
            "niveau": "CONFIRME",
            "charge_pourcentage": 100.0,
        }
    ],
}

# 7 semaines x 35 h x 0,5 = 122,5 heures par poste.
HOURS_PER_POSITION = 122.5


class TeamCompatibilityTests(TestCase):
    """Seuil de compatibilité et distinction dotation / couverture."""

    def setUp(self):
        """Prépare le projet mobile et son analyse."""
        self.owner = make_owner("mobileowner")
        self.project = make_project(self.owner)
        make_analysis(self.project, MOBILE_ANALYSIS)

    def test_compatible_candidate_is_assigned_and_covers_the_skill(self):
        """Un candidat dont les compétences couvrent la spécialité est retenu."""
        make_freelancer("mobiledev", skills=["Mobile", "Android"], hourly_rate=18)
        team = build_team(self.project, MOBILE_ANALYSIS)
        self.assertTrue(team["fully_staffed"])
        self.assertTrue(team["fully_covered"])
        self.assertEqual(team["assigned_positions"], 1)
        self.assertEqual(team["skill_covered_positions"], 1)
        self.assertEqual(team["members"][0]["skill_score"], 100.0)
        self.assertEqual(team["members"][0]["missing_skills"], [])

    def test_weakly_compatible_candidate_is_not_assigned(self):
        """Le cas observé : un profil back-end ne prend pas le poste mobile."""
        make_freelancer(
            "backend", skills=["Python", "Django"], hourly_rate=50
        )
        team = build_team(self.project, MOBILE_ANALYSIS)
        self.assertFalse(team["fully_staffed"])
        self.assertFalse(team["fully_covered"])
        self.assertEqual(team["assigned_positions"], 0)
        self.assertEqual(team["members"], [])
        self.assertEqual(len(team["uncovered"]), 1)
        self.assertEqual(
            team["uncovered"][0]["reason"],
            "aucun_candidat_suffisamment_compatible",
        )

    def test_rejected_candidate_is_still_reported(self):
        """Le meilleur candidat écarté reste visible : rien n'est supprimé."""
        make_freelancer("backend2", skills=["Python"], hourly_rate=50)
        team = build_team(self.project, MOBILE_ANALYSIS)
        best = team["uncovered"][0]["best_candidate"]
        self.assertEqual(best["username"], "backend2")
        self.assertEqual(best["skill_score"], 0.0)
        self.assertIn("mobile", best["missing_skills"])
        self.assertTrue(
            any("suffisamment compatible" in alert for alert in team["alerts"])
        )

    def test_missing_skill_is_reported_on_an_assigned_member(self):
        """Un poste attribué sans couverture est compté séparément."""
        make_freelancer("hybride", skills=["Python"], hourly_rate=18)
        with override_settings(MATCHING_TEAM_MIN_SCORE=0):
            team = build_team(self.project, MOBILE_ANALYSIS)
        self.assertTrue(team["fully_staffed"])
        self.assertFalse(team["fully_covered"])
        self.assertEqual(team["assigned_positions"], 1)
        self.assertEqual(team["skill_covered_positions"], 0)
        self.assertFalse(team["members"][0]["skill_covered"])
        self.assertIn("mobile", team["members"][0]["missing_skills"])
        self.assertTrue(
            any("ne couvrent" in alert for alert in team["alerts"])
        )

    def test_threshold_is_configurable(self):
        """Le seuil global se règle et change le résultat de la composition."""
        make_freelancer("mobiledev2", skills=["Mobile"], hourly_rate=18)
        with override_settings(MATCHING_TEAM_MIN_SCORE=0):
            permissive = build_team(self.project, MOBILE_ANALYSIS)
        with override_settings(MATCHING_TEAM_MIN_SCORE=95):
            strict = build_team(self.project, MOBILE_ANALYSIS)
        self.assertEqual(permissive["assigned_positions"], 1)
        self.assertEqual(strict["assigned_positions"], 0)
        self.assertEqual(strict["assumptions"]["score_minimal"], 95.0)
        self.assertEqual(
            strict["uncovered"][0]["reason"],
            "aucun_candidat_suffisamment_compatible",
        )

    @override_settings(MATCHING_TEAM_MIN_SCORE=0, MATCHING_TEAM_MIN_SKILL_SCORE=0)
    def test_skill_threshold_is_configurable(self):
        """Un seuil de compétences nul déclare tout poste attribué couvert."""
        make_freelancer("anyone", skills=["Python"], hourly_rate=18)
        team = build_team(self.project, MOBILE_ANALYSIS)
        self.assertTrue(team["fully_staffed"])
        self.assertTrue(team["fully_covered"])


class TeamBudgetTests(TestCase):
    """Coût estimé, hypothèses explicites et comparaison au budget."""

    def setUp(self):
        """Prépare le projet mobile et son analyse."""
        self.owner = make_owner("budgetowner")
        self.project = make_project(self.owner)
        make_analysis(self.project, MOBILE_ANALYSIS)

    def test_assumptions_are_explicit(self):
        """Durée, heures par semaine, engagement et volume horaire sont exposés."""
        make_freelancer("mobilecheap", skills=["Mobile"], hourly_rate=18)
        team = build_team(self.project, MOBILE_ANALYSIS)
        assumptions = team["assumptions"]
        self.assertEqual(assumptions["duree_semaines"], 7)
        self.assertEqual(assumptions["heures_par_semaine"], 35.0)
        self.assertEqual(assumptions["taux_engagement"], 0.5)
        self.assertEqual(assumptions["heures_par_poste"], HOURS_PER_POSITION)

    def test_cost_within_budget_raises_no_alert(self):
        """Un tarif compatible produit un coût inférieur au budget."""
        make_freelancer("mobilecheap2", skills=["Mobile"], hourly_rate=18)
        team = build_team(self.project, MOBILE_ANALYSIS)
        self.assertEqual(team["estimated_cost"], round(18 * HOURS_PER_POSITION, 2))
        self.assertEqual(team["budget_total"], 2500.0)
        self.assertEqual(team["budget_source"], "budget_recommande")
        self.assertFalse(team["over_budget"])
        self.assertFalse(any("budget" in alert for alert in team["alerts"]))

    def test_cost_above_budget_is_flagged(self):
        """Un tarif élevé déclenche l'alerte de dépassement budgétaire."""
        make_freelancer("mobilepricey", skills=["Mobile"], hourly_rate=40)
        with override_settings(MATCHING_TEAM_MIN_SCORE=0):
            team = build_team(self.project, MOBILE_ANALYSIS)
        self.assertEqual(team["estimated_cost"], round(40 * HOURS_PER_POSITION, 2))
        self.assertTrue(team["over_budget"])
        self.assertTrue(
            any("dépasse le budget" in alert for alert in team["alerts"])
        )

    def test_cost_compares_totals_not_hourly_rates(self):
        """Le coût comparé au budget est un montant total, jamais un tarif."""
        make_freelancer("mobilerate", skills=["Mobile"], hourly_rate=18)
        team = build_team(self.project, MOBILE_ANALYSIS)
        self.assertGreater(team["estimated_cost"], 18)
        self.assertEqual(
            team["estimated_cost"],
            round(18 * team["assumptions"]["heures_par_poste"], 2),
        )

    def test_missing_rate_marks_cost_as_partial(self):
        """Un membre sans tarif rend l'estimation de coût partielle."""
        make_freelancer("mobilenorate", skills=["Mobile"], hourly_rate=None)
        team = build_team(self.project, MOBILE_ANALYSIS)
        self.assertTrue(team["estimated_cost_partial"])

    def test_budget_falls_back_to_project_amount(self):
        """Sans budget dans l'analyse, le montant du projet sert de référence."""
        analysis = copy.deepcopy(MOBILE_ANALYSIS)
        analysis.pop("budget_recommande")
        analysis.pop("budget_max")
        make_freelancer("mobilefallback", skills=["Mobile"], hourly_rate=18)
        team = build_team(self.project, analysis)
        self.assertEqual(team["budget_source"], "montant_estime_projet")
        self.assertEqual(team["budget_total"], 10000.0)


class TeamStructureTests(TestCase):
    """Couverture multi-spécialités et unicité des affectations."""

    def setUp(self):
        """Prépare un projet analysé demandant deux spécialités."""
        self.owner = make_owner("teamowner")
        self.project = make_project(self.owner)
        make_analysis(self.project)

    def test_team_is_empty_without_candidates(self):
        """Sans freelance validé, aucune spécialité n'est pourvue."""
        team = build_team(self.project, ANALYSIS_RESULT)
        self.assertFalse(team["fully_staffed"])
        self.assertEqual(team["assigned_positions"], 0)
        self.assertEqual(len(team["uncovered"]), 2)
        self.assertEqual(
            team["uncovered"][0]["reason"], "aucun_candidat_disponible"
        )

    def test_team_is_complete_when_every_post_is_covered(self):
        """Deux freelances pertinents couvrent les deux spécialités."""
        make_freelancer("py", skills=["Python"], hourly_rate=30)
        make_freelancer("react", skills=["React"], hourly_rate=30)
        team = build_team(self.project, ANALYSIS_RESULT)
        self.assertTrue(team["fully_staffed"])
        self.assertTrue(team["fully_covered"])
        self.assertEqual(team["assigned_positions"], 2)
        self.assertEqual(team["skill_covered_positions"], 2)
        self.assertEqual(team["uncovered"], [])

    def test_a_freelancer_is_never_assigned_twice(self):
        """Un même freelance ne peut pas occuper deux postes."""
        make_freelancer("solo", skills=["Python", "React"], hourly_rate=30)
        team = build_team(self.project, ANALYSIS_RESULT)
        assigned = [member["freelancer_id"] for member in team["members"]]
        self.assertEqual(len(assigned), len(set(assigned)))
        self.assertFalse(team["fully_staffed"])

    def test_unvalidated_freelancer_is_never_selected(self):
        """Un profil non validé n'entre pas dans une équipe."""
        pending = make_freelancer(
            "pendingteam",
            skills=["Python"],
            moderation_status=User.ModerationStatus.PENDING,
        )
        team = build_team(self.project, ANALYSIS_RESULT)
        selected = {member["freelancer_id"] for member in team["members"]}
        self.assertNotIn(pending.pk, selected)

    def test_analysis_without_speciality_is_reported(self):
        """Une analyse sans spécialité ne produit jamais une équipe complète."""
        team = build_team(self.project, {"duree_semaines": 5, "specialites": []})
        self.assertFalse(team["fully_staffed"])
        self.assertEqual(team["required_positions"], 0)
        self.assertTrue(any("aucune spécialité" in a for a in team["alerts"]))


class TeamEndpointTests(APITestCase):
    """Accès à la proposition d'équipe par l'API."""

    def setUp(self):
        """Prépare un projet analysé et son porteur."""
        self.owner = make_owner("teamapi")
        self.project = make_project(self.owner)
        make_analysis(self.project)
        make_freelancer("apipy", skills=["Python"], hourly_rate=25)

    def authenticate(self, user):
        """Authentifie le client de test."""
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_owner_reads_team_proposal(self):
        """Le porteur obtient une proposition d'équipe structurée."""
        self.authenticate(self.owner)
        response = self.client.get(
            f"/api/matching/projects/{self.project.pk}/team/"
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["required_positions"], 2)
        self.assertFalse(payload["fully_staffed"])
        self.assertTrue(payload["uncovered"])
        self.assertIn("heures_par_poste", payload["assumptions"])

    def test_freelancer_cannot_read_team_proposal(self):
        """Un freelance ne peut pas consulter la composition d'équipe."""
        freelancer = make_freelancer("teamspy")
        self.authenticate(freelancer)
        response = self.client.get(
            f"/api/matching/projects/{self.project.pk}/team/"
        )
        self.assertEqual(response.status_code, 403)
