from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


REQUIRED_FIELDS = (
    "messageId",
    "roomId",
    "userId",
    "username",
    "content",
    "timestamp",
)


@dataclass(frozen=True)
class IncomingMessage:
    message_id: str
    room_id: str
    user_id: str
    username: str
    content: str
    timestamp: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "IncomingMessage":
        missing = [field for field in REQUIRED_FIELDS if field not in payload]
        if missing:
            raise ValueError(f"Campos obrigatorios ausentes: {', '.join(missing)}")

        values = {field: payload[field] for field in REQUIRED_FIELDS}
        if not all(isinstance(value, str) for value in values.values()):
            raise ValueError("Todos os campos da mensagem devem ser strings")

        if not values["messageId"].strip() or not values["roomId"].strip():
            raise ValueError("messageId e roomId nao podem ser vazios")
        if not values["content"].strip():
            raise ValueError("content nao pode ser vazio")
        if len(values["content"]) > 4000:
            raise ValueError("content excede 4000 caracteres")

        normalized_timestamp = values["timestamp"].replace("Z", "+00:00")
        try:
            datetime.fromisoformat(normalized_timestamp)
        except ValueError as exc:
            raise ValueError("timestamp deve estar em formato ISO 8601") from exc

        return cls(
            message_id=values["messageId"],
            room_id=values["roomId"],
            user_id=values["userId"],
            username=values["username"],
            content=values["content"],
            timestamp=values["timestamp"],
        )

    def public_message(self) -> dict[str, str]:
        return {
            "id": self.message_id,
            "roomId": self.room_id,
            "userId": self.user_id,
            "username": self.username,
            "content": self.content,
            "createdAt": self.timestamp,
        }

    def sns_event(self) -> dict[str, str]:
        return {
            "eventType": "message.created",
            "roomId": self.room_id,
            "messageId": self.message_id,
            "username": self.username,
            "preview": self.content[:50],
            "timestamp": self.timestamp,
        }

