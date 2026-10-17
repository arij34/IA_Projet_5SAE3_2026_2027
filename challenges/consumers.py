"""Authenticated WebSocket delivery for generated supervisor messages."""

from asgiref.sync import async_to_sync
from channels.generic.websocket import JsonWebsocketConsumer

from challenges.models import QuizAttempt, SupervisorEvent
from challenges.services.supervisor_delivery import (
    SUPERVISOR_WEBSOCKET_PROTOCOL,
    acknowledge_supervisor_event,
    consume_supervisor_connection_ticket,
    supervisor_attempt_group,
    ticket_from_subprotocols,
)

DELIVERABLE_STATUSES = (
    SupervisorEvent.GenerationStatus.GENERATED,
    SupervisorEvent.GenerationStatus.FALLBACK,
)


class SupervisorConsumer(JsonWebsocketConsumer):
    """Expose only the current owner's validated supervisor messages."""

    def connect(self):
        self.attempt_id = self.scope["url_route"]["kwargs"]["attempt_id"]
        ticket = ticket_from_subprotocols(self.scope.get("subprotocols", []))
        user = consume_supervisor_connection_ticket(ticket, self.attempt_id) if ticket else None
        if user is None or not self._attempt_is_active_owner(user.pk):
            self.close(code=4401)
            return

        self.user_id = user.pk
        self.group_name = supervisor_attempt_group(self.attempt_id)
        async_to_sync(self.channel_layer.group_add)(
            self.group_name,
            self.channel_name,
        )
        self.accept(subprotocol=SUPERVISOR_WEBSOCKET_PROTOCOL)
        self._replay_unacknowledged()

    def disconnect(self, close_code):
        group_name = getattr(self, "group_name", None)
        if group_name is not None:
            async_to_sync(self.channel_layer.group_discard)(
                group_name,
                self.channel_name,
            )

    def receive_json(self, content, **kwargs):
        if (
            not isinstance(content, dict)
            or content.get("type") != "ack"
            or isinstance(content.get("event_id"), bool)
            or not isinstance(content.get("event_id"), int)
        ):
            self.close(code=4400)
            return

        acknowledged = acknowledge_supervisor_event(
            self.attempt_id,
            content["event_id"],
            self.user_id,
        )
        if not acknowledged:
            self.close(code=4403)
            return
        self.send_json(
            {
                "type": "supervisor.acknowledged",
                "event_id": content["event_id"],
            }
        )

    def supervisor_event(self, content):
        self._send_event(content["event_id"])

    def supervisor_attempt_completed(self, content):
        self.close(code=1000)

    def _attempt_is_active_owner(self, user_id):
        return QuizAttempt.objects.filter(
            pk=self.attempt_id,
            user_id=user_id,
            status=QuizAttempt.Status.IN_PROGRESS,
        ).exists()

    def _replay_unacknowledged(self):
        event_ids = SupervisorEvent.objects.filter(
            attempt_id=self.attempt_id,
            attempt__user_id=self.user_id,
            attempt__status=QuizAttempt.Status.IN_PROGRESS,
            generation_status__in=DELIVERABLE_STATUSES,
            acknowledged_at__isnull=True,
        ).order_by("created_at", "pk").values_list("pk", flat=True)
        for event_id in event_ids:
            self._send_event(event_id)

    def _send_event(self, event_id):
        event = SupervisorEvent.objects.filter(
            pk=event_id,
            attempt_id=self.attempt_id,
            attempt__user_id=self.user_id,
            attempt__status=QuizAttempt.Status.IN_PROGRESS,
            generation_status__in=DELIVERABLE_STATUSES,
            acknowledged_at__isnull=True,
        ).first()
        if event is None:
            return

        self.send_json(
            {
                "type": "supervisor.event",
                "event": {
                    "id": event.pk,
                    "attempt_id": event.attempt_id,
                    "trigger_type": event.trigger_type,
                    "message": event.message,
                    "prompt_version": event.prompt_version,
                    "generation_status": event.generation_status,
                    "created_at": event.created_at.isoformat(),
                },
            }
        )
