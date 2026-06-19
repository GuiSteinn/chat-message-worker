from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .models import IncomingMessage


class MessageProcessor:
    """Processa uma mensagem com checkpoints simples para retries."""

    def __init__(
        self,
        collection: Any,
        redis_client: Any,
        sns_client: Any,
        sns_topic_arn: str,
        recent_limit: int = 50,
    ) -> None:
        self.collection = collection
        self.redis = redis_client
        self.sns = sns_client
        self.sns_topic_arn = sns_topic_arn
        self.recent_limit = recent_limit

    def process(self, message: IncomingMessage) -> dict[str, str]:
        public_message = message.public_message()
        now = datetime.now(timezone.utc)

        self.collection.update_one(
            {"id": message.message_id},
            {
                "$setOnInsert": {
                    **public_message,
                    "delivery": {
                        "redisPublished": False,
                        "snsPublished": False,
                    },
                    "insertedAt": now,
                }
            },
            upsert=True,
        )

        stored = self.collection.find_one(
            {"id": message.message_id},
            {"delivery": 1},
        ) or {}
        delivery = stored.get("delivery", {})

        serialized = json.dumps(
            public_message,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

        if not delivery.get("redisPublished", False):
            pipeline = self.redis.pipeline(transaction=True)
            recent_key = f"room:{message.room_id}:recent"
            pipeline.lrem(recent_key, 0, serialized)
            pipeline.lpush(recent_key, serialized)
            pipeline.ltrim(recent_key, 0, self.recent_limit - 1)
            pipeline.publish(f"room:{message.room_id}", serialized)
            pipeline.execute()
            self.collection.update_one(
                {"id": message.message_id},
                {"$set": {"delivery.redisPublished": True}},
            )

        if not delivery.get("snsPublished", False):
            self.sns.publish(
                TopicArn=self.sns_topic_arn,
                Message=json.dumps(
                    message.sns_event(),
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                Subject="Nova mensagem no chat",
            )
            self.collection.update_one(
                {"id": message.message_id},
                {"$set": {"delivery.snsPublished": True}},
            )

        self.collection.update_one(
            {"id": message.message_id},
            {"$set": {"processedAt": now}},
        )
        return public_message

