"""Ticket authentication and persisted event delivery for supervisor sockets."""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta

from asgiref.sync import async_to_sync
from channels.exceptions import ChannelFull, InvalidChannelLayerError
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from redis.exceptions import RedisError

from challenges.models import (
    QuizAttempt,
    SupervisorConnectionTicket,
    SupervisorEvent,
)

SUPERVISOR_TICKET_TTL_SECONDS = 60
SUPERVISOR_WEBSOCKET_PROTOCOL = "freelancy.supervisor.v1"
_TICKET_PROTOCOL_PREFIX = "ticket."
_DELIVERABLE_STATUSES = (
    SupervisorEvent.GenerationStatus.GENERATED,
    SupervisorEvent.GenerationStatus.FALLBACK,
)

logger = logging.getLogger(__name__)


def supervisor_attempt_group(attempt_id: int) -> str:
    return f"supervisor_attempt_{attempt_id}"


def create_supervisor_connection_ticket(
    user,
    attempt: QuizAttempt,
) -> tuple[str, datetime]:
    """Return a plaintext ticket once while persisting only its digest."""
    token = secrets.token_urlsafe(32)
    expires_at = timezone.now() + timedelta(
        seconds=SUPERVISOR_TICKET_TTL_SECONDS
    )
    SupervisorConnectionTicket.objects.create(
        user=user,
        attempt=attempt,
        token_digest=hashlib.sha256(token.encode("utf-8")).hexdigest(),
        expires_at=expires_at,
    )
    return token, expires_at


def consume_supervisor_connection_ticket(
    token: str,
    attempt_id: int,
):
    """Atomically consume a valid ticket bound to an active owned attempt."""
    if not isinstance(token, str) or not token or len(token) > 128:
        return None

    now = timezone.now()
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    with transaction.atomic():
        ticket = (
            SupervisorConnectionTicket.objects.select_for_update()
            .select_related("user", "attempt")
            .filter(
                token_digest=digest,
                attempt_id=attempt_id,
                expires_at__gt=now,
                consumed_at__isnull=True,
            )
            .first()
        )
        if ticket is None:
            return None

        user = ticket.user
        attempt = ticket.attempt
        if (
            attempt.user_id != user.pk
            or attempt.status != QuizAttempt.Status.IN_PROGRESS
            or not user.is_active
            or user.role != get_user_model().Role.FREELANCER
            or user.moderation_status != get_user_model().ModerationStatus.OK
        ):
            return None

        consumed = SupervisorConnectionTicket.objects.filter(
            pk=ticket.pk,
            expires_at__gt=now,
            consumed_at__isnull=True,
        ).update(consumed_at=now)
        if consumed != 1:
            return None
    return user


def acknowledge_supervisor_event(
    attempt_id: int,
    event_id: int,
    user_id: int,
) -> bool:
    """Persist an owner-scoped receipt acknowledgment; duplicate acks are safe."""
    eligible = SupervisorEvent.objects.filter(
        pk=event_id,
        attempt_id=attempt_id,
        attempt__user_id=user_id,
        generation_status__in=_DELIVERABLE_STATUSES,
        attempt__status=QuizAttempt.Status.IN_PROGRESS,
    )
    if not eligible.exists():
        return False

    acknowledged_at = timezone.now()
    updated = eligible.filter(acknowledged_at__isnull=True).update(
        acknowledged_at=acknowledged_at,
    )
    return updated == 1 or eligible.filter(acknowledged_at__isnull=False).exists()


def _publish(attempt_id: int, message: dict) -> bool:
    try:
        channel_layer = get_channel_layer()
        if channel_layer is None:
            logger.error("Supervisor channel layer is not configured.")
            return False
        async_to_sync(channel_layer.group_send)(
            supervisor_attempt_group(attempt_id),
            message,
        )
    except (
        ChannelFull,
        InvalidChannelLayerError,
        RedisError,
        OSError,
        RuntimeError,
    ) as error:
        logger.error(
            "Supervisor event dispatch failed (%s).",
            type(error).__name__,
        )
        return False
    return True


def publish_supervisor_event(event_id: int) -> bool:
    """Signal a persisted, unacknowledged message; consumers reload its payload."""
    event = (
        SupervisorEvent.objects.select_related("attempt")
        .filter(
            pk=event_id,
            generation_status__in=_DELIVERABLE_STATUSES,
            acknowledged_at__isnull=True,
            attempt__status=QuizAttempt.Status.IN_PROGRESS,
        )
        .first()
    )
    if event is None:
        return False
    return _publish(
        event.attempt_id,
        {"type": "supervisor.event", "event_id": event.pk},
    )


def publish_attempt_completed(attempt_id: int) -> bool:
    return _publish(
        attempt_id,
        {"type": "supervisor.attempt_completed"},
    )


def ticket_from_subprotocols(protocols: list[str]) -> str | None:
    """Extract only the short-lived ticket protocol; never accept URL credentials."""
    if SUPERVISOR_WEBSOCKET_PROTOCOL not in protocols:
        return None
    candidates = [
        protocol[len(_TICKET_PROTOCOL_PREFIX):]
        for protocol in protocols
        if protocol.startswith(_TICKET_PROTOCOL_PREFIX)
    ]
    return candidates[0] if len(candidates) == 1 else None
