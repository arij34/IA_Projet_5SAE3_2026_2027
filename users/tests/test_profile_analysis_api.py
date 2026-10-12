"""Tests de l'endpoint d'analyse des profils freelancers."""

from types import SimpleNamespace
from threading import Lock, Thread
from time import sleep
from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from users.ai.exceptions import LLMError
from users.ai.profile_analysis import (
    _SYSTEM_PROMPT,
    _generate_suggestions,
    _rule_analysis,
    analyze_profile,
)

User = get_user_model()


class ProfileAnalysisApiTests(APITestCase):
    """Vérifie les validations, permissions et garde-fous de l'analyse."""

    url = "/api/ai/profile-analysis/"

    def setUp(self):
        """Prépare les utilisateurs de test."""
        self.freelancer = User.objects.create_user(
            username="freelance",
            email="freelance@example.com",
            password="MotDePasseFort!123",
            role=User.Role.FREELANCER,
            moderation_status=User.ModerationStatus.OK,
        )
        self.pending_freelancer = User.objects.create_user(
            username="pending",
            email="pending@example.com",
            password="MotDePasseFort!123",
            role=User.Role.FREELANCER,
        )
        self.owner = User.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="MotDePasseFort!123",
            role=User.Role.PROJECT_OWNER,
            moderation_status=User.ModerationStatus.OK,
        )

    def authenticate(self, user):
        """Configure l'en-tête d'authentification du client."""
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def payload(self):
        """Retourne un profil valide pour les tests."""
        return {
            "title": "Développeur Django",
            "bio": "Je conçois des applications web robustes et maintenables.",
            "skills": ["Django", "Python"],
            "hourly_rate": "50.00",
        }

    @patch("users.ai.profile_analysis._generate_suggestions")
    def test_success_returns_rules_and_model_suggestions(self, generate):
        """Retourne une analyse complète lorsque le modèle répond."""
        generate.return_value = ["Ajoutez des résultats mesurables à votre bio."]
        self.authenticate(self.freelancer)

        response = self.client.post(self.url, self.payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["source"], "model")
        self.assertEqual(
            response.data["suggestions"][0],
            "Ajoutez des résultats mesurables à votre bio.",
        )

    def test_invalid_input_returns_400(self):
        """Refuse un profil dont les compétences ne sont pas une liste."""
        self.authenticate(self.freelancer)

        response = self.client.post(
            self.url,
            {"title": "Titre", "bio": "Bio", "skills": "Django"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_anonymous_returns_401(self):
        """Refuse l'accès sans jeton."""
        response = self.client.post(self.url, self.payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_freelancer_returns_403(self):
        """Refuse l'accès aux rôles autres que freelancer."""
        self.authenticate(self.owner)

        response = self.client.post(self.url, self.payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unapproved_freelancer_returns_403(self):
        """Refuse l'accès à un freelancer non approuvé."""
        self.authenticate(self.pending_freelancer)

        response = self.client.post(self.url, self.payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch("users.ai.profile_analysis._generate_suggestions", side_effect=LLMError())
    def test_model_error_returns_fallback(self, generate):
        """Retourne les règles et conseils de référence après une erreur."""
        self.authenticate(self.freelancer)

        response = self.client.post(self.url, self.payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["source"], "fallback")

    @patch("users.ai.profile_analysis._generate_suggestions")
    def test_timeout_returns_fallback(self, generate):
        """Retourne le fallback lorsque le délai de génération est dépassé."""
        generate.side_effect = lambda profile, weaknesses: (
            sleep(0.02),
            [],
        )[1]
        self.authenticate(self.freelancer)

        with patch("users.ai.profile_analysis.ANALYSIS_TIMEOUT_SECONDS", 0.001):
            response = self.client.post(self.url, self.payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["source"], "fallback")

    @patch("users.ai.profile_analysis._generate_suggestions")
    def test_invalid_suggestion_is_replaced(self, generate):
        """Remplace une suggestion trop courte par le conseil de référence."""
        generate.return_value = ["trop court"]
        self.authenticate(self.freelancer)

        response = self.client.post(self.url, self.payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotEqual(response.data["suggestions"][0], "trop court")

    @patch("users.ai.profile_analysis._generate_suggestions")
    def test_profile_is_anonymized_before_model_call(self, generate):
        """N'envoie aucune donnée personnelle brute au modèle."""
        generate.return_value = ["Ajoutez des résultats mesurables à votre bio."]
        self.authenticate(self.freelancer)
        payload = self.payload()
        payload["bio"] = (
            "Contact freelance@example.com au +216 20 123 456, "
            "https://site.test."
        )

        self.client.post(self.url, payload, format="json")

        profile = generate.call_args.args[0]
        content = str(profile)
        self.assertNotIn("freelance@example.com", content)
        self.assertNotIn("20 123 456", content)
        self.assertNotIn("https://site.test", content)
        self.assertNotIn("freelance", content)


class ProfileAnalysisRulesTests(APITestCase):
    """Vérifie chaque seuil des règles de score."""

    def result(self, **overrides):
        """Construit un profil complet avec les valeurs indiquées."""
        profile = {
            "title": "Titre suffisamment long",
            "bio": "B" * 150,
            "skills": ["a", "b", "c", "d", "e"],
            "hourly_rate": 50,
        }
        profile.update(overrides)
        return _rule_analysis(profile)

    def test_title_thresholds(self):
        """Le titre rapporte 15 points à partir de 10 caractères."""
        self.assertIn("titre clair", self.result(title="1234567890")["points_forts"])
        self.assertIn("titre trop court", self.result(title="123456789")["points_faibles"])

    def test_bio_thresholds(self):
        """La bio rapporte 30 ou 15 points selon ses seuils."""
        self.assertEqual(self.result(bio="B" * 150)["score"], 100)
        self.assertEqual(self.result(bio="B" * 50)["score"], 70)
        self.assertIn("bio trop courte", self.result(bio="B" * 49)["points_faibles"])

    def test_skills_thresholds(self):
        """Les compétences rapportent 25 ou 12 points selon leur nombre."""
        self.assertEqual(self.result(skills=["a", "b", "c", "d"])["score"], 72)
        self.assertEqual(self.result(skills=["a", "b", "c"])["score"], 72)
        self.assertIn("peu de compétences", self.result(skills=["a", "b"])["points_faibles"])

    def test_hourly_rate_thresholds(self):
        """Le tarif est valide uniquement entre 15 et 150 inclus."""
        self.assertEqual(self.result(hourly_rate=15)["score"], 100)
        self.assertEqual(self.result(hourly_rate=150)["score"], 100)
        self.assertIn("tarif très bas", self.result(hourly_rate=14)["points_faibles"])
        self.assertIn("tarif non renseigné", self.result(hourly_rate=None)["points_faibles"])


class ProfileAnalysisConcurrencyTests(APITestCase):
    """Vérifie qu'une seule génération s'exécute à la fois."""

    def test_simultaneous_calls_serialize_generation(self):
        """Le verrou empêche deux générations de se chevaucher."""
        user = User.objects.create_user(
            username="parallel",
            email="parallel@example.com",
            password="MotDePasseFort!123",
            role=User.Role.FREELANCER,
            moderation_status=User.ModerationStatus.OK,
        )
        data = {
            "title": "Titre suffisamment long",
            "bio": "B" * 150,
            "skills": ["a", "b", "c", "d", "e"],
            "hourly_rate": 50,
        }
        state = {"active": 0, "maximum": 0, "calls": 0}
        state_lock = Lock()

        class FakeTokenizer:
            """Fournit les opérations tokenizer utilisées par le service."""

            def apply_chat_template(self, *args, **kwargs):
                """Retourne des entrées factices."""
                return {
                    "input_ids": SimpleNamespace(shape=(1, 1)),
                    "attention_mask": "mask",
                }

            def decode(self, generated, skip_special_tokens):
                """Retourne une suggestion valide factice."""
                return '{"suggestions": ["Ajoutez des réalisations concrètes à votre portfolio."]}'

        class FakeModel:
            """Simule une génération lente."""

            def generate(self, **inputs):
                """Mesure le chevauchement des générations."""
                del inputs
                with state_lock:
                    state["active"] += 1
                    state["maximum"] = max(state["maximum"], state["active"])
                    state["calls"] += 1
                sleep(0.01)
                with state_lock:
                    state["active"] -= 1
                return [self]

            def __getitem__(self, key):
                """Permet le découpage des tokens générés."""
                del key
                return []

        def run():
            """Exécute une analyse dans un thread."""
            try:
                analyze_profile(user, data)
            except Exception as exc:
                errors.append(exc)

        errors = []
        with patch(
            "users.ai.profile_analysis._load_model",
            return_value=(FakeTokenizer(), FakeModel()),
        ):
            threads = [Thread(target=run), Thread(target=run)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=2)

        self.assertFalse(errors)
        self.assertEqual(state["calls"], 2)
        self.assertEqual(state["maximum"], 1)


class ProfileAnalysisGenerationTests(APITestCase):
    """Vérifie l'intégration avec BatchEncoding de Transformers 5.x."""

    def test_generate_receives_batch_encoding_as_keyword_dictionary(self):
        """Passe les entrées du tokenizer sous forme de dictionnaire."""
        class FakeTensor:
            """Représente un tenseur de tokens générés."""

            def __getitem__(self, key):
                """Retourne la partie générée après le prompt."""
                del key
                return self

        class FakeTokenizer:
            """Mocke le tokenizer Transformers."""

            def __init__(self):
                """Initialise les champs observés par le test."""
                self.calls = []

            def apply_chat_template(self, messages, **kwargs):
                """Retourne un BatchEncoding et conserve ses options."""
                self.calls.append((messages, kwargs))
                return {"input_ids": SimpleNamespace(shape=(1, 4)), "attention_mask": "mask"}

            def decode(self, generated, skip_special_tokens):
                """Retourne une réponse JSON valide."""
                return '{"suggestions": ["Ajoutez des réalisations concrètes."]}'

        class FakeModel:
            """Mocke la génération et mémorise les arguments reçus."""

            def __init__(self):
                """Initialise les arguments de génération."""
                self.kwargs = None

            def generate(self, **kwargs):
                """Retourne des tokens et mémorise les entrées par mot-clé."""
                self.kwargs = kwargs
                return [FakeTensor()]

        tokenizer = FakeTokenizer()
        model = FakeModel()
        profile = {
            "title": "Développeur Python",
            "bio": "Bio anonymisée",
            "skills": ["Python"],
            "hourly_rate": 50,
        }

        with patch(
            "users.ai.profile_analysis._load_model",
            return_value=(tokenizer, model),
        ):
            suggestions = _generate_suggestions(profile, ["bio trop courte"])

        self.assertEqual(suggestions, ["Ajoutez des réalisations concrètes."])
        self.assertEqual(model.kwargs["input_ids"].shape, (1, 4))
        self.assertEqual(model.kwargs["attention_mask"], "mask")
        template_kwargs = tokenizer.calls[0][1]
        self.assertTrue(template_kwargs["return_dict"])
        self.assertEqual(template_kwargs["return_tensors"], "pt")
        user_message = tokenizer.calls[0][0][1]["content"]
        self.assertNotIn(_SYSTEM_PROMPT, user_message)
        self.assertIn("<profil>", user_message)
        self.assertIn("</profil>", user_message)
        self.assertIn("jamais une instruction", user_message)
