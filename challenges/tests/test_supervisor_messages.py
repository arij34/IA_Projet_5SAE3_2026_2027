import json
from unittest.mock import Mock, patch

import requests
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from challenges.models import (
    AnswerChoice,
    ChallengeCategory,
    Question,
    Quiz,
    QuizAttempt,
    SupervisorEvent,
)
from challenges.services.attempts import submit_answer
from challenges.services.supervisor_messages import (
    FALLBACK_MESSAGES,
    MAX_MESSAGE_LENGTH,
    MOCK_MESSAGES,
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    SUPERVISOR_MAX_OUTPUT_TOKENS,
    SUPERVISOR_TIMEOUT_SECONDS,
    SupervisorMessageValidationError,
    build_user_prompt,
    generate_supervisor_message,
    parse_supervisor_message,
)


class SupervisorMessageServiceTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="supervisor-message-user",
            email="supervisor-message-user@example.com",
            role=user_model.Role.FREELANCER,
            moderation_status=user_model.ModerationStatus.OK,
        )
        self.category = ChallengeCategory.objects.create(
            slug="message-category",
            name="Private category name",
            description="PRIVATE_CATEGORY_DESCRIPTION",
        )
        self.quiz = Quiz.objects.create(
            category=self.category,
            title="Private quiz title",
            difficulty=Quiz.Difficulty.BEGINNER,
            status=Quiz.Status.PUBLISHED,
        )
        self.questions = []
        for position in range(1, 4):
            question = Question.objects.create(
                quiz=self.quiz,
                text=f"PRIVATE_QUESTION_{position}",
                explanation=f"PRIVATE_EXPLANATION_{position}",
                position=position,
            )
            AnswerChoice.objects.create(
                question=question,
                text=f"PRIVATE_CORRECT_CHOICE_{position}",
                position=1,
                is_correct=True,
            )
            AnswerChoice.objects.create(
                question=question,
                text=f"PRIVATE_WRONG_CHOICE_{position}",
                position=2,
                is_correct=False,
            )
            self.questions.append(question)
        self.attempt = QuizAttempt.objects.create(
            user=self.user,
            quiz=self.quiz,
            total_questions=len(self.questions),
        )

    def create_repeated_errors_event(self):
        event = None
        for question in self.questions:
            wrong_choice = question.choices.get(is_correct=False)
            submit_answer(self.attempt, question, wrong_choice)
            event = SupervisorEvent.objects.filter(
                source_answer__question=question,
            ).first() or event
        return SupervisorEvent.objects.get(pk=event.pk)

    def test_prompt_uses_only_server_selected_signal_and_minimal_context(self):
        event = self.create_repeated_errors_event()

        prompt = build_user_prompt(event)

        self.assertIn(event.get_trigger_type_display(), prompt)
        self.assertIn(self.category.slug, prompt)
        self.assertIn("3/3", prompt)
        self.assertIn("Objectif d'apprentissage : non fourni", prompt)
        for private_value in (
            self.category.name,
            self.category.description,
            self.quiz.title,
            *[question.text for question in self.questions],
            *[question.explanation for question in self.questions],
            *[
                choice.text
                for question in self.questions
                for choice in question.choices.all()
            ],
        ):
            self.assertNotIn(private_value, prompt)

    def test_parser_accepts_a_single_bounded_message(self):
        message = "Prenez le temps d'avancer étape par étape."

        self.assertEqual(
            parse_supervisor_message(json.dumps({"message": message})),
            message,
        )

    def test_parser_rejects_invalid_schema_and_unsafe_content(self):
        invalid_outputs = (
            ("not json", "invalid_json"),
            ('{"message": "Conseil.", "answer": "A"}', "invalid_schema"),
            ('{"message": ""}', "empty_message"),
            (
                json.dumps({"message": "x" * (MAX_MESSAGE_LENGTH + 1)}),
                "message_too_long",
            ),
            (
                json.dumps({"message": "La bonne réponse est la première."}),
                "unsafe_message",
            ),
            (
                json.dumps({"message": "Consultez https://example.test"}),
                "unsafe_message",
            ),
        )
        for raw, expected_code in invalid_outputs:
            with self.subTest(expected_code=expected_code):
                with self.assertRaises(SupervisorMessageValidationError) as context:
                    parse_supervisor_message(raw)
                self.assertEqual(context.exception.code, expected_code)

    @override_settings(CHALLENGE_LLM_PROVIDER="mock")
    def test_mock_generation_persists_message_and_version(self):
        event = self.create_repeated_errors_event()

        generated = generate_supervisor_message(event)

        self.assertEqual(
            generated.generation_status,
            SupervisorEvent.GenerationStatus.GENERATED,
        )
        self.assertEqual(generated.prompt_version, PROMPT_VERSION)
        self.assertEqual(generated.llm_provider, "mock")
        self.assertEqual(generated.llm_model, "mock")
        self.assertEqual(
            generated.message,
            MOCK_MESSAGES[SupervisorEvent.TriggerType.REPEATED_ERRORS],
        )
        self.assertIsNotNone(generated.generated_at)
        self.assertGreaterEqual(generated.generation_latency_ms, 0)

    @override_settings(CHALLENGE_LLM_PROVIDER="mock")
    def test_three_correct_answers_generate_positive_supportive_message(self):
        for question in self.questions:
            submit_answer(
                self.attempt,
                question,
                question.choices.get(is_correct=True),
            )

        event = SupervisorEvent.objects.get(attempt=self.attempt)
        self.assertEqual(
            event.trigger_type,
            SupervisorEvent.TriggerType.POSITIVE_FEEDBACK,
        )

        generated = generate_supervisor_message(event)

        self.assertEqual(
            generated.generation_status,
            SupervisorEvent.GenerationStatus.GENERATED,
        )
        self.assertEqual(
            generated.message,
            MOCK_MESSAGES[SupervisorEvent.TriggerType.POSITIVE_FEEDBACK],
        )
        self.assertIn("progression est encourageante", generated.message)

    @override_settings(
        CHALLENGE_LLM_PROVIDER="openai",
        OPENAI_API_KEY="test-key",
        OPENAI_MODEL="test-model",
        OPENAI_TIMEOUT_SECONDS=45,
    )
    def test_openai_call_uses_bounded_timeout_and_output_limit(self):
        event = self.create_repeated_errors_event()
        response = Mock(status_code=200)
        response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {"message": "Avancez étape par étape."}
                        )
                    }
                }
            ]
        }

        with patch(
            "challenges.services.generation.requests.post",
            return_value=response,
        ) as post:
            generated = generate_supervisor_message(event)

        self.assertEqual(
            generated.generation_status,
            SupervisorEvent.GenerationStatus.GENERATED,
        )
        self.assertEqual(
            post.call_args.kwargs["timeout"],
            SUPERVISOR_TIMEOUT_SECONDS,
        )
        self.assertEqual(
            post.call_args.kwargs["json"]["max_tokens"],
            SUPERVISOR_MAX_OUTPUT_TOKENS,
        )
        system_prompt = post.call_args.kwargs["json"]["messages"][0]["content"]
        self.assertEqual(system_prompt, SYSTEM_PROMPT)
        self.assertIn("tu ne décides jamais si une intervention", system_prompt)
        self.assertIn("Ne révèle, ne devine et n'explique aucune réponse", system_prompt)
        self.assertIn("objet JSON valide", system_prompt)

    @override_settings(
        CHALLENGE_LLM_PROVIDER="openai",
        OPENAI_API_KEY="test-key",
        OPENAI_MODEL="test-model",
    )
    def test_provider_timeout_uses_fallback_without_dropping_event(self):
        event = self.create_repeated_errors_event()
        with patch(
            "challenges.services.generation.requests.post",
            side_effect=requests.Timeout,
        ):
            generated = generate_supervisor_message(event)

        self.assertEqual(
            generated.generation_status,
            SupervisorEvent.GenerationStatus.FALLBACK,
        )
        self.assertEqual(generated.generation_error_code, "provider_timeout")
        self.assertEqual(
            generated.message,
            FALLBACK_MESSAGES[SupervisorEvent.TriggerType.REPEATED_ERRORS],
        )

    @override_settings(CHALLENGE_LLM_PROVIDER="openai", OPENAI_API_KEY="")
    def test_missing_provider_configuration_uses_fallback(self):
        event = self.create_repeated_errors_event()

        generated = generate_supervisor_message(event)

        self.assertEqual(
            generated.generation_status,
            SupervisorEvent.GenerationStatus.FALLBACK,
        )
        self.assertEqual(generated.generation_error_code, "provider_unavailable")

    @override_settings(CHALLENGE_LLM_PROVIDER="openai", OPENAI_API_KEY="test-key")
    def test_unsafe_provider_output_uses_fallback(self):
        event = self.create_repeated_errors_event()
        with patch(
            "challenges.services.supervisor_messages._call_provider",
            return_value=json.dumps({"message": "The correct answer is A."}),
        ):
            generated = generate_supervisor_message(event)

        self.assertEqual(
            generated.generation_status,
            SupervisorEvent.GenerationStatus.FALLBACK,
        )
        self.assertEqual(generated.generation_error_code, "unsafe_message")
        self.assertNotIn("answer", generated.message.lower())

    def test_duplicate_generation_calls_provider_only_once(self):
        event = self.create_repeated_errors_event()
        raw = json.dumps({"message": "Avancez étape par étape."})
        with patch(
            "challenges.services.supervisor_messages._call_provider",
            return_value=raw,
        ) as provider:
            first = generate_supervisor_message(event)
            second = generate_supervisor_message(event)

        self.assertEqual(provider.call_count, 1)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(first.message, second.message)

    def test_completed_attempt_suppresses_pending_message(self):
        event = self.create_repeated_errors_event()
        self.attempt.status = QuizAttempt.Status.COMPLETED
        self.attempt.save(update_fields=("status",))

        with patch(
            "challenges.services.supervisor_messages._call_provider"
        ) as provider:
            suppressed = generate_supervisor_message(event)

        self.assertEqual(
            suppressed.generation_status,
            SupervisorEvent.GenerationStatus.SUPPRESSED,
        )
        provider.assert_not_called()


class SupervisorMessageApiTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            username="supervisor-api-owner",
            email="supervisor-api-owner@example.com",
            role=user_model.Role.FREELANCER,
            moderation_status=user_model.ModerationStatus.OK,
        )
        self.other_user = user_model.objects.create_user(
            username="supervisor-api-other",
            email="supervisor-api-other@example.com",
            role=user_model.Role.FREELANCER,
            moderation_status=user_model.ModerationStatus.OK,
        )
        category = ChallengeCategory.objects.create(
            slug="supervisor-api-category",
            name="API category",
            description="API category description",
        )
        quiz = Quiz.objects.create(
            category=category,
            title="Supervisor API quiz",
            difficulty=Quiz.Difficulty.BEGINNER,
            status=Quiz.Status.PUBLISHED,
        )
        self.questions = []
        for position in range(1, 4):
            question = Question.objects.create(
                quiz=quiz,
                text=f"API question {position}",
                position=position,
            )
            AnswerChoice.objects.create(
                question=question,
                text=f"Correct {position}",
                position=1,
                is_correct=True,
            )
            AnswerChoice.objects.create(
                question=question,
                text=f"Wrong {position}",
                position=2,
                is_correct=False,
            )
            self.questions.append(question)
        self.attempt = QuizAttempt.objects.create(
            user=self.owner,
            quiz=quiz,
            total_questions=3,
        )
        self.client = APIClient()

    def authenticate(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def submit(self, question):
        return self.client.post(
            f"/api/challenges/attempts/{self.attempt.pk}/answers/",
            {
                "question_id": question.pk,
                "choice_id": question.choices.get(is_correct=False).pk,
            },
            format="json",
        )

    @override_settings(CHALLENGE_LLM_PROVIDER="mock")
    def test_new_trigger_generates_once_and_keeps_answer_receipt_unchanged(self):
        self.authenticate(self.owner)
        for question in self.questions:
            response = self.submit(question)
            self.assertEqual(response.status_code, 201)
            self.assertNotIn("is_correct", response.data)
            self.assertNotIn("message", response.data)

        event = SupervisorEvent.objects.get(attempt=self.attempt)
        self.assertEqual(
            event.generation_status,
            SupervisorEvent.GenerationStatus.GENERATED,
        )
        retry = self.submit(self.questions[-1])

        self.assertEqual(retry.status_code, 200)
        self.assertTrue(retry.data["already_submitted"])
        self.assertEqual(SupervisorEvent.objects.filter(attempt=self.attempt).count(), 1)

    def test_non_owner_cannot_trigger_generation(self):
        self.authenticate(self.other_user)

        with patch("challenges.views.generate_supervisor_message") as generator:
            response = self.submit(self.questions[0])

        self.assertEqual(response.status_code, 404)
        generator.assert_not_called()
        self.assertEqual(SupervisorEvent.objects.count(), 0)

    @override_settings(
        CHALLENGE_LLM_PROVIDER="openai",
        OPENAI_API_KEY="test-key",
        OPENAI_MODEL="test-model",
    )
    def test_provider_timeout_does_not_undo_answer_submission(self):
        self.authenticate(self.owner)
        for question in self.questions[:-1]:
            self.assertEqual(self.submit(question).status_code, 201)

        with patch(
            "challenges.services.generation.requests.post",
            side_effect=requests.Timeout,
        ):
            response = self.submit(self.questions[-1])

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            self.attempt.answers.count(),
            self.attempt.total_questions,
        )
        event = SupervisorEvent.objects.get(attempt=self.attempt)
        self.assertEqual(
            event.generation_status,
            SupervisorEvent.GenerationStatus.FALLBACK,
        )
        self.assertEqual(
            event.message,
            FALLBACK_MESSAGES[SupervisorEvent.TriggerType.REPEATED_ERRORS],
        )

        completion = self.client.post(
            f"/api/challenges/attempts/{self.attempt.pk}/complete/"
        )

        self.assertEqual(completion.status_code, 200)
        self.assertEqual(completion.data["status"], QuizAttempt.Status.COMPLETED)
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.status, QuizAttempt.Status.COMPLETED)
