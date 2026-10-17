from django.urls import path

from challenges.consumers import SupervisorConsumer

websocket_urlpatterns = [
    path(
        "ws/challenges/attempts/<int:attempt_id>/supervisor/",
        SupervisorConsumer.as_asgi(),
        name="challenge-supervisor",
    ),
]
