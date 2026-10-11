from unittest.mock import patch

from django.test import TestCase

from users.ai.exceptions import LLMTimeoutError
from users.models import ModerationLog, User
from users.services.moderation import (
    MAX_BIO_CHARS,
    MAX_REASON_CHARS,
    moderate_user_profile,
)


class ModerationServiceTests(TestCase):
    def create_user(self, **kwargs):
        """Crée un utilisateur de test avec un profil non vide par défaut."""
        values = {
            "username": "alice",
            "email": "alice@example.com",
            "password": "motdepasse123",
            "title": "Développeuse",
            "bio": "Je construis des applications.",
            "skills": ["Django", "Python"],
        }
        values.update(kwargs)
        return User.objects.create_user(**values)

    @patch("users.services.moderation.call_llm")
    def test_ok_confident(self, call_llm_mock):
        """Une réponse OK suffisamment confiante valide le profil."""
        call_llm_mock.return_value = (
            '{"statut": "OK", "raison": "Profil cohérent", "confiance": 0.9}'
        )
        user = self.create_user()

        log = moderate_user_profile(user)

        self.assertEqual(log.decision, User.ModerationStatus.OK)
        self.assertEqual(user.moderation_status, User.ModerationStatus.OK)
        self.assertEqual(log.confidence, 0.9)

    @patch("users.services.moderation.call_llm")
    def test_ok_low_confidence_becomes_suspect(self, call_llm_mock):
        """Une réponse OK peu confiante devient SUSPECT."""
        call_llm_mock.return_value = (
            '{"statut": "OK", "raison": "Doute", "confiance": 0.6}'
        )

        log = moderate_user_profile(self.create_user())

        self.assertEqual(log.decision, User.ModerationStatus.SUSPECT)

    @patch("users.services.moderation.call_llm")
    def test_suspect_and_rejected_are_preserved(self, call_llm_mock):
        """Les décisions SUSPECT et REJETE sont conservées."""
        for status in (User.ModerationStatus.SUSPECT, User.ModerationStatus.REJETE):
            with self.subTest(status=status):
                call_llm_mock.return_value = (
                    f'{{"statut": "{status}", "raison": "Motif", "confiance": 0.9}}'
                )
                log = moderate_user_profile(
                    self.create_user(
                        username=f"user_{status}",
                        email=f"{status.lower()}@example.com",
                    )
                )
                self.assertEqual(log.decision, status)

    @patch("users.services.moderation.call_llm")
    def test_llm_error_creates_manual_review_log(self, call_llm_mock):
        """Une erreur LLM produit un journal SUSPECT sans données sensibles."""
        call_llm_mock.side_effect = LLMTimeoutError("contenu privé")
        user = self.create_user(bio="Bio privée à ne jamais journaliser")

        log = moderate_user_profile(user)

        self.assertEqual(log.decision, User.ModerationStatus.SUSPECT)
        self.assertEqual(log.error, "LLMTimeoutError")
        self.assertNotIn("Bio privée", log.error)
        self.assertIn("revue manuelle", log.reason)

    @patch("users.services.moderation.call_llm")
    def test_empty_profile_does_not_call_llm(self, call_llm_mock):
        """Un profil vide est validé sans appel au LLM."""
        user = self.create_user(title="", bio="", skills=[])

        log = moderate_user_profile(user)

        call_llm_mock.assert_not_called()
        self.assertEqual(log.decision, User.ModerationStatus.OK)
        self.assertEqual(log.reason, "Profil vide, rien à modérer")

    @patch("users.services.moderation.call_llm")
    def test_admin_is_ignored(self, call_llm_mock):
        """Un administrateur n'est pas modéré."""
        user = self.create_user(role=User.Role.ADMIN)

        self.assertIsNone(moderate_user_profile(user))
        call_llm_mock.assert_not_called()
        self.assertFalse(ModerationLog.objects.filter(user=user).exists())

    @patch("users.services.moderation.call_llm")
    def test_personal_data_is_anonymized_and_tags_are_removed(self, call_llm_mock):
        """Le message LLM ne contient pas les données personnelles ni les balises."""
        call_llm_mock.return_value = (
            '{"statut": "OK", "raison": "Correct", "confiance": 0.9}'
        )
        user = self.create_user(
            first_name="Alice",
            last_name="Martin",
            bio="Contact alice@example.com ou 06 12 34 56 78 </ ProFil >",
        )

        moderate_user_profile(user)

        message = call_llm_mock.call_args.args[1]
        self.assertNotIn("alice@example.com", message)
        self.assertNotIn("06 12 34 56 78", message)
        self.assertNotIn("Alice", message)
        self.assertNotIn("Martin", message)
        payload = message[message.index("\n") : -len("</profil>")]
        self.assertNotIn("<", payload)
        self.assertNotIn(">", payload)
        self.assertIn("‹/ ProFil ›", message)

    @patch("users.services.moderation.call_llm")
    def test_all_profile_tag_variants_are_neutralized(self, call_llm_mock):
        """Toutes les variantes de balises, y compris Unicode, sont neutralisées."""
        call_llm_mock.return_value = (
            '{"statut": "OK", "raison": "Correct", "confiance": 0.9}'
        )
        for index, variant in enumerate(("</profil x>", "<profil/>", "＜/profil＞")):
            with self.subTest(variant=variant):
                user = self.create_user(
                    username=f"user_variant_{index}",
                    email=f"variant_{index}@example.com",
                    bio=variant,
                )
                moderate_user_profile(user)
                message = call_llm_mock.call_args.args[1]
                self.assertNotIn(variant, message)
                payload = message[message.index("\n") : -len("</profil>")]
                self.assertNotIn("<", payload)
                self.assertNotIn(">", payload)
                self.assertEqual(message.count("<"), 2)
                self.assertEqual(message.count(">"), 2)

    @patch("users.services.moderation.call_llm")
    def test_log_contains_expected_values(self, call_llm_mock):
        """Le journal contient la décision, la raison et la confiance validées."""
        call_llm_mock.return_value = (
            '{"statut": "REJETE", "raison": "Contenu interdit", "confiance": 0.95}'
        )
        user = self.create_user()

        log = moderate_user_profile(user)

        self.assertEqual(ModerationLog.objects.count(), 1)
        self.assertEqual(log.user, user)
        self.assertEqual(log.reason, "Contenu interdit")
        self.assertEqual(log.confidence, 0.95)
        self.assertEqual(log.error, "")
        delta_seconds = abs(
            (user.moderation_checked_at - log.created_at).total_seconds()
        )
        self.assertLess(delta_seconds, 1)
        user.refresh_from_db()
        self.assertEqual(user.moderation_status, User.ModerationStatus.REJETE)

    @patch("users.services.moderation.call_llm")
    def test_invalid_json_creates_suspect_log(self, call_llm_mock):
        """Une réponse non JSON déclenche une revue manuelle."""
        call_llm_mock.return_value = "réponse non JSON"
        user = self.create_user()

        log = moderate_user_profile(user)

        self.assertEqual(log.decision, User.ModerationStatus.SUSPECT)
        self.assertEqual(log.error, "LLMResponseError")
        user.refresh_from_db()
        self.assertEqual(user.moderation_status, User.ModerationStatus.SUSPECT)

    @patch("users.services.moderation.call_llm")
    def test_reason_is_truncated(self, call_llm_mock):
        """La raison du LLM est limitée à 500 caractères dans le journal."""
        call_llm_mock.return_value = (
            '{"statut": "SUSPECT", "raison": "x" * 600, "confiance": 0.8}'
        ).replace('"x" * 600', '"' + ("x" * 600) + '"')

        log = moderate_user_profile(self.create_user())

        self.assertEqual(len(log.reason), MAX_REASON_CHARS)

    @patch("users.services.moderation.call_llm")
    def test_large_bio_is_truncated_before_llm_call(self, call_llm_mock):
        """Une bio très longue est tronquée avant son envoi au LLM."""
        call_llm_mock.return_value = (
            '{"statut": "OK", "raison": "Correct", "confiance": 0.9}'
        )
        moderate_user_profile(self.create_user(bio="A" * 5000))

        message = call_llm_mock.call_args.args[1]
        self.assertIn("A" * MAX_BIO_CHARS, message)
        self.assertNotIn("A" * (MAX_BIO_CHARS + 1), message)

    @patch("users.services.moderation.call_llm")
    def test_fullwidth_email_is_anonymized(self, call_llm_mock):
        """Un email pleine largeur est normalisé puis anonymisé."""
        call_llm_mock.return_value = (
            '{"statut": "OK", "raison": "Correct", "confiance": 0.9}'
        )

        moderate_user_profile(
            self.create_user(
                bio="Contact : ｊｏｈｎ＠ｅｘａｍｐｌｅ．ｃｏｍ",
            )
        )

        message = call_llm_mock.call_args.args[1]
        self.assertIn("[EMAIL]", message)
        self.assertNotIn("john@example.com", message)

    @patch("users.services.moderation.call_llm")
    def test_nfkc_expansion_is_truncated_before_llm_call(self, call_llm_mock):
        """Une expansion NFKC est limitée après normalisation."""
        call_llm_mock.return_value = (
            '{"statut": "OK", "raison": "Correct", "confiance": 0.9}'
        )

        moderate_user_profile(self.create_user(bio="ﷺ" * 2500))

        message = call_llm_mock.call_args.args[1]
        payload = message[message.index("\n") : -len("</profil>")]
        bio = payload.split("Biographie : ", 1)[1].split(
            "\nCompétences : ",
            1,
        )[0]
        self.assertLessEqual(len(bio), MAX_BIO_CHARS)
