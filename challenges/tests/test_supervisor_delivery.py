import hashlib
from datetime import timedelta
from unittest.mock import patch

from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient
from redis.exceptions import RedisError

from challenges.models import (
    AnswerChoice,
    ChallengeCategory,
    Question,
    Quiz,
    QuizAttempt,
    SupervisorConnectionTicket,
    SupervisorEvent,
)
from config.asgi import application

WS_PROTOCOL = "freelancy.supervisor.v1"
ALLOWED_ORIGIN = "http://localhost:5173"


class SupervisorTicketApiTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            username="ticket-owner",
            email="ticket-owner@example.com",
            role=user_model.Role.FREELANCER,
            moderation_status=user_model.ModerationStatus.OK,
        )
        self.other = user_model.objects.create_user(
            username="ticket-other",
            email="ticket-other@example.com",
            role=user_model.Role.FREELANCER,
            moderation_status=user_model.ModerationStatus.OK,
        )
        self.pending = user_model.objects.create_user(
            username="ticket-pending",
            email="ticket-pending@example.com",
            role=user_model.Role.FREELANCER,
            moderation_status=user_model.ModerationStatus.PENDING,
        )
        category = ChallengeCategory.objects.create(
            slug="ticket-category",
            name="Ticket category",
            description="Ticket tests",
        )
        quiz = Quiz.objects.create(
            category=category,
            title="Ticket quiz",
            difficulty=Quiz.Difficulty.BEGINNER,
            status=Quiz.Status.PUBLISHED,
        )
        self.attempt = QuizAttempt.objects.create(
            user=self.owner,
            quiz=quiz,
            total_questions=1,
        )
        self.client = APIClient()

    def authenticate(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_owner_receives_short_lived_ticket_without_persisting_plaintext(self):
        self.authenticate(self.owner)

        response = self.client.post(
            f"/api/challenges/attempts/{self.attempt.pk}/supervisor-ticket/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(set(response.data), {"ticket", "expires_at"})
        ticket = response.data["ticket"]
        record = SupervisorConnectionTicket.objects.get(attempt=self.attempt)
        self.assertEqual(
            record.token_digest,
            hashlib.sha256(ticket.encode("utf-8")).hexdigest(),
        )
        self.assertNotEqual(record.token_digest, ticket)
        self.assertGreater(record.expires_at, timezone.now())
        self.assertLessEqual(
            record.expires_at,
            timezone.now() + timedelta(seconds=61),
        )

    def test_anonymous_non_owner_unapproved_and_completed_attempts_are_rejected(self):
        anonymous = self.client.post(
            f"/api/challenges/attempts/{self.attempt.pk}/supervisor-ticket/",
            {},
            format="json",
        )
        self.assertEqual(anonymous.status_code, status.HTTP_401_UNAUTHORIZED)

        self.authenticate(self.other)
        non_owner = self.client.post(
            f"/api/challenges/attempts/{self.attempt.pk}/supervisor-ticket/",
            {},
            format="json",
        )
        self.assertEqual(non_owner.status_code, status.HTTP_404_NOT_FOUND)

        self.authenticate(self.pending)
        unapproved = self.client.post(
            f"/api/challenges/attempts/{self.attempt.pk}/supervisor-ticket/",
            {},
            format="json",
        )
        self.assertEqual(unapproved.status_code, status.HTTP_403_FORBIDDEN)

        self.authenticate(self.owner)
        self.attempt.status = QuizAttempt.Status.COMPLETED
        self.attempt.save(update_fields=("status",))
        completed = self.client.post(
            f"/api/challenges/attempts/{self.attempt.pk}/supervisor-ticket/",
            {},
            format="json",
        )
        self.assertEqual(completed.status_code, status.HTTP_409_CONFLICT)

    def test_ticket_storage_failure_returns_503_not_500(self):
        from django.db import OperationalError

        self.authenticate(self.owner)
        with patch(
            "challenges.views.create_supervisor_connection_ticket",
            side_effect=OperationalError("no such table"),
        ):
            with self.assertLogs("challenges.views", level="ERROR"):
                response = self.client.post(
                    f"/api/challenges/attempts/{self.attempt.pk}/supervisor-ticket/",
                    {},
                    format="json",
                )

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertNotIn("ticket", response.data)


@override_settings(
    CHANNEL_LAYERS={
        "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"},
    },
    CHALLENGE_LLM_PROVIDER="mock",
)
class SupervisorDeliveryWebsocketTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            username="ws-owner",
            email="ws-owner@example.com",
            role=user_model.Role.FREELANCER,
            moderation_status=user_model.ModerationStatus.OK,
        )
        self.other = user_model.objects.create_user(
            username="ws-other",
            email="ws-other@example.com",
            role=user_model.Role.FREELANCER,
            moderation_status=user_model.ModerationStatus.OK,
        )
        category = ChallengeCategory.objects.create(
            slug="ws-category",
            name="WebSocket category",
            description="WebSocket tests",
        )
        self.quiz = Quiz.objects.create(
            category=category,
            title="WebSocket quiz",
            difficulty=Quiz.Difficulty.BEGINNER,
            status=Quiz.Status.PUBLISHED,
        )
        self.questions = []
        self.wrong_choice_ids = []
        for position in range(1, 4):
            question = Question.objects.create(
                quiz=self.quiz,
                text=f"Question {position}",
                position=position,
            )
            AnswerChoice.objects.create(
                question=question,
                text=f"Correct {position}",
                position=1,
                is_correct=True,
            )
            wrong_choice = AnswerChoice.objects.create(
                question=question,
                text=f"Wrong {position}",
                position=2,
                is_correct=False,
            )
            self.questions.append(question)
            self.wrong_choice_ids.append(wrong_choice.pk)
        self.attempt = QuizAttempt.objects.create(
            user=self.owner,
            quiz=self.quiz,
            total_questions=3,
        )
        self.client = APIClient()
        token, _ = Token.objects.get_or_create(user=self.owner)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def issue_ticket(self, attempt_id=None):
        return self.client.post(
            f"/api/challenges/attempts/{attempt_id or self.attempt.pk}/supervisor-ticket/",
            {},
            format="json",
        )

    def communicator(self, ticket, *, attempt_id=None, origin=ALLOWED_ORIGIN):
        protocols = [WS_PROTOCOL]
        if ticket:
            protocols.append(f"ticket.{ticket}")
        return WebsocketCommunicator(
            application,
            f"/ws/challenges/attempts/{attempt_id or self.attempt.pk}/supervisor/",
            subprotocols=protocols,
            headers=[(b"origin", origin.encode("ascii"))],
        )

    async def submit_repeated_errors(self):
        for question, wrong_choice_id in zip(
            self.questions,
            self.wrong_choice_ids,
        ):
            response = await sync_to_async(self.client.post, thread_sensitive=True)(
                f"/api/challenges/attempts/{self.attempt.pk}/answers/",
                {
                    "question_id": question.pk,
                    "choice_id": wrong_choice_id,
                },
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return await sync_to_async(
            SupervisorEvent.objects.get,
            thread_sensitive=True,
        )(attempt=self.attempt)

    async def test_owner_receives_live_event_acknowledges_and_stops_replay(self):
        ticket_response = await sync_to_async(
            self.issue_ticket,
            thread_sensitive=True,
        )()
        self.assertEqual(ticket_response.status_code, status.HTTP_201_CREATED)
        communicator = self.communicator(ticket_response.data["ticket"])
        connected, selected_protocol = await communicator.connect()
        self.assertTrue(connected)
        self.assertEqual(selected_protocol, WS_PROTOCOL)

        event = await self.submit_repeated_errors()
        delivered = await communicator.receive_json_from(timeout=1)
        self.assertEqual(delivered["type"], "supervisor.event")
        self.assertEqual(delivered["event"]["id"], event.pk)
        self.assertEqual(delivered["event"]["attempt_id"], self.attempt.pk)

        await communicator.send_json_to(
            {"type": "ack", "event_id": event.pk},
        )
        self.assertEqual(
            await communicator.receive_json_from(timeout=1),
            {"type": "supervisor.acknowledged", "event_id": event.pk},
        )
        await sync_to_async(event.refresh_from_db, thread_sensitive=True)()
        self.assertIsNotNone(event.acknowledged_at)
        await communicator.send_json_to(
            {"type": "ack", "event_id": event.pk},
        )
        self.assertEqual(
            await communicator.receive_json_from(timeout=1),
            {"type": "supervisor.acknowledged", "event_id": event.pk},
        )
        await communicator.disconnect()

        reconnect_ticket = await sync_to_async(
            self.issue_ticket,
            thread_sensitive=True,
        )()
        reconnect = self.communicator(reconnect_ticket.data["ticket"])
        self.assertTrue((await reconnect.connect())[0])
        replayed = await reconnect.receive_json_from(timeout=1)
        self.assertEqual(replayed["event"]["id"], event.pk)
        await reconnect.disconnect()

    async def test_unacknowledged_event_is_replayed_with_minimal_payload(self):
        event = await self.submit_repeated_errors()
        ticket_response = await sync_to_async(
            self.issue_ticket,
            thread_sensitive=True,
        )()
        communicator = self.communicator(ticket_response.data["ticket"])

        self.assertTrue((await communicator.connect())[0])
        delivered = await communicator.receive_json_from(timeout=1)
        self.assertEqual(delivered["type"], "supervisor.event")
        self.assertEqual(
            set(delivered["event"]),
            {
                "id",
                "attempt_id",
                "trigger_type",
                "message",
                "prompt_version",
                "generation_status",
                "llm_provider",
                "generation_error_code",
                "created_at",
            },
        )
        self.assertIn(
            delivered["event"]["generation_status"],
            {
                SupervisorEvent.GenerationStatus.GENERATED,
                SupervisorEvent.GenerationStatus.FALLBACK,
            },
        )
        self.assertEqual(delivered["event"]["id"], event.pk)
        self.assertNotIn("is_correct", delivered["event"])
        self.assertNotIn("error", delivered["event"])
        await communicator.disconnect()

        retry_ticket = await sync_to_async(
            self.issue_ticket,
            thread_sensitive=True,
        )()
        replay = self.communicator(retry_ticket.data["ticket"])
        self.assertTrue((await replay.connect())[0])
        self.assertEqual(
            (await replay.receive_json_from(timeout=1))["event"]["id"],
            event.pk,
        )
        await replay.disconnect()

    async def test_wrong_attempt_ack_is_rejected_and_does_not_change_other_event(self):
        other_attempt = await sync_to_async(QuizAttempt.objects.create, thread_sensitive=True)(
            user=self.other,
            quiz=self.quiz,
            total_questions=3,
        )
        other_answer = await sync_to_async(
            self._create_answer_for_other_attempt,
            thread_sensitive=True,
        )(other_attempt)
        other_event = await sync_to_async(
            SupervisorEvent.objects.create,
            thread_sensitive=True,
        )(
            attempt=other_attempt,
            source_answer=other_answer,
            trigger_type=SupervisorEvent.TriggerType.REPEATED_ERRORS,
            event_key="other-attempt:ack:event",
            slot=1,
            generation_status=SupervisorEvent.GenerationStatus.GENERATED,
            message="Private to another attempt",
            prompt_version="quiz-supervisor-v1",
        )
        ticket_response = await sync_to_async(
            self.issue_ticket,
            thread_sensitive=True,
        )()
        communicator = self.communicator(ticket_response.data["ticket"])
        self.assertTrue((await communicator.connect())[0])

        await communicator.send_json_to(
            {"type": "ack", "event_id": other_event.pk},
        )
        close_message = await communicator.receive_output(timeout=1)
        self.assertEqual(close_message["type"], "websocket.close")
        await sync_to_async(other_event.refresh_from_db, thread_sensitive=True)()
        self.assertIsNone(other_event.acknowledged_at)

    async def test_completion_closes_active_delivery_connection(self):
        ticket_response = await sync_to_async(
            self.issue_ticket,
            thread_sensitive=True,
        )()
        communicator = self.communicator(ticket_response.data["ticket"])
        self.assertTrue((await communicator.connect())[0])
        await self.submit_repeated_errors()
        await communicator.receive_json_from(timeout=1)

        completed = await sync_to_async(self.client.post, thread_sensitive=True)(
            f"/api/challenges/attempts/{self.attempt.pk}/complete/",
        )

        self.assertEqual(completed.status_code, status.HTTP_200_OK)
        close_message = await communicator.receive_output(timeout=1)
        self.assertEqual(close_message["type"], "websocket.close")
        await communicator.disconnect()

    async def test_answer_submission_survives_channel_layer_failure(self):
        for question, wrong_choice_id in zip(
            self.questions[:-1],
            self.wrong_choice_ids[:-1],
        ):
            response = await sync_to_async(self.client.post, thread_sensitive=True)(
                f"/api/challenges/attempts/{self.attempt.pk}/answers/",
                {
                    "question_id": question.pk,
                    "choice_id": wrong_choice_id,
                },
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        with self.assertLogs(
            "challenges.services.supervisor_delivery",
            level="ERROR",
        ) as captured:
            with patch(
                "challenges.services.supervisor_delivery.get_channel_layer",
                side_effect=RedisError("do not log this provider detail"),
            ):
                response = await sync_to_async(
                    self.client.post,
                    thread_sensitive=True,
                )(
                    f"/api/challenges/attempts/{self.attempt.pk}/answers/",
                    {
                        "question_id": self.questions[-1].pk,
                        "choice_id": self.wrong_choice_ids[-1],
                    },
                    format="json",
                )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotIn(
            "do not log this provider detail",
            "\n".join(captured.output),
        )
        self.assertEqual(
            await sync_to_async(self.attempt.answers.count, thread_sensitive=True)(),
            self.attempt.total_questions,
        )

    async def test_invalid_origin_missing_ticket_reuse_and_completed_attempt_rejected(self):
        ticket_response = await sync_to_async(
            self.issue_ticket,
            thread_sensitive=True,
        )()
        ticket = ticket_response.data["ticket"]

        invalid_origin = self.communicator(ticket, origin="https://attacker.example")
        self.assertFalse((await invalid_origin.connect())[0])

        no_ticket = self.communicator(None)
        self.assertFalse((await no_ticket.connect())[0])

        mismatched_attempt = await sync_to_async(
            QuizAttempt.objects.create,
            thread_sensitive=True,
        )(
            user=self.other,
            quiz=self.quiz,
            total_questions=3,
        )
        wrong_scope = self.communicator(ticket, attempt_id=mismatched_attempt.pk)
        self.assertFalse((await wrong_scope.connect())[0])

        first = self.communicator(ticket)
        self.assertTrue((await first.connect())[0])
        await first.disconnect()
        reused = self.communicator(ticket)
        self.assertFalse((await reused.connect())[0])

        expired_response = await sync_to_async(
            self.issue_ticket,
            thread_sensitive=True,
        )()
        expired_record = await sync_to_async(
            SupervisorConnectionTicket.objects.get,
            thread_sensitive=True,
        )(attempt=self.attempt, consumed_at__isnull=True)
        await sync_to_async(
            SupervisorConnectionTicket.objects.filter(pk=expired_record.pk).update,
            thread_sensitive=True,
        )(expires_at=timezone.now() - timedelta(seconds=1))
        expired = self.communicator(expired_response.data["ticket"])
        self.assertFalse((await expired.connect())[0])

        self.attempt.status = QuizAttempt.Status.COMPLETED
        await sync_to_async(self.attempt.save, thread_sensitive=True)(
            update_fields=("status",),
        )
        completed_ticket = await sync_to_async(
            self.issue_ticket,
            thread_sensitive=True,
        )()
        self.assertEqual(completed_ticket.status_code, status.HTTP_409_CONFLICT)

    async def test_event_from_another_attempt_is_not_delivered_on_this_group(self):
        other_attempt = await sync_to_async(QuizAttempt.objects.create, thread_sensitive=True)(
            user=self.other,
            quiz=self.quiz,
            total_questions=3,
        )
        ticket_response = await sync_to_async(
            self.issue_ticket,
            thread_sensitive=True,
        )()
        communicator = self.communicator(ticket_response.data["ticket"])
        self.assertTrue((await communicator.connect())[0])

        from challenges.services.supervisor_delivery import publish_supervisor_event

        other_event = await sync_to_async(
            SupervisorEvent.objects.create,
            thread_sensitive=True,
        )(
            attempt=other_attempt,
            source_answer=await sync_to_async(
                self._create_answer_for_other_attempt,
                thread_sensitive=True,
            )(other_attempt),
            trigger_type=SupervisorEvent.TriggerType.REPEATED_ERRORS,
            event_key="other-attempt:test:event",
            slot=1,
            generation_status=SupervisorEvent.GenerationStatus.GENERATED,
            message="Private to another attempt",
            prompt_version="quiz-supervisor-v1",
        )
        await sync_to_async(publish_supervisor_event, thread_sensitive=True)(other_event.pk)

        self.assertTrue(await communicator.receive_nothing(timeout=0.05))
        await communicator.disconnect()

    def _create_answer_for_other_attempt(self, attempt):
        from challenges.models import SubmittedAnswer

        question = self.questions[0]
        return SubmittedAnswer.objects.create(
            attempt=attempt,
            question=question,
            selected_choice=question.choices.get(is_correct=False),
            is_correct=False,
        )
