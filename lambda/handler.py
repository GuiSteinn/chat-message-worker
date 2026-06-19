import json
import logging
from typing import Any


LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    notifications = []

    for record in event.get("Records", []):
        sns = record.get("Sns", {})
        raw_message = sns.get("Message", "{}")
        try:
            message = json.loads(raw_message)
        except json.JSONDecodeError:
            LOGGER.warning("Evento SNS invalido: %s", raw_message)
            continue

        notification = {
            "kind": "offline-notification-simulated",
            "roomId": message.get("roomId"),
            "messageId": message.get("messageId"),
            "text": (
                f"Nova mensagem de {message.get('username', 'usuario')}: "
                f"{message.get('preview', '')}"
            ),
        }
        notifications.append(notification)
        LOGGER.info(
            "NOTIFICATION %s",
            json.dumps(notification, ensure_ascii=False),
        )

    return {
        "statusCode": 200,
        "processed": len(notifications),
        "notifications": notifications,
    }

