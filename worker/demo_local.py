"""Demonstra o processamento sem depender de uma conta AWS.

Usa MongoDB e Redis locais via Docker Compose. O SNS e substituido por um
objeto que imprime o evento no terminal. O fluxo interno e o mesmo do worker.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from pymongo import MongoClient
from redis import Redis


sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.models import IncomingMessage
from app.processor import MessageProcessor


class SnsLocal:
    def publish(self, **kwargs):
        print("\n[SNS simulado] Evento publicado:")
        print(json.dumps(json.loads(kwargs["Message"]), indent=2, ensure_ascii=False))
        return {"MessageId": "sns-local-1"}


def load_dotenv() -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def main() -> None:
    load_dotenv()
    mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017/chat")
    redis_url = os.getenv("REDIS_URL", "redis://:chatredis@localhost:6379/0")

    mongo = MongoClient(mongo_uri, serverSelectionTimeoutMS=3000)
    mongo.admin.command("ping")
    collection = mongo["chat"]["messages"]
    collection.create_index("id", unique=True)

    redis_client = Redis.from_url(redis_url, decode_responses=True)
    redis_client.ping()

    processor = MessageProcessor(
        collection=collection,
        redis_client=redis_client,
        sns_client=SnsLocal(),
        sns_topic_arn=os.getenv(
            "SNS_TOPIC_ARN",
            "arn:aws:sns:us-east-1:000000000000:chat-notifications",
        ),
    )

    payload = {
        "messageId": "demo-guilherme-001",
        "roomId": "sala-sistemas-distribuidos",
        "userId": "guilherme-stein",
        "username": "Guilherme",
        "content": "Mensagem processada pelo worker do Guilherme!",
        "timestamp": "2026-06-19T18:00:00Z",
    }

    print("[Entrada equivalente ao SQS]")
    print(json.dumps(payload, indent=2, ensure_ascii=False))

    result = processor.process(IncomingMessage.from_dict(payload))

    saved = collection.find_one({"id": result["id"]}, {"_id": 0})
    recent = redis_client.lrange(
        f"room:{payload['roomId']}:recent",
        0,
        -1,
    )

    print("\n[MongoDB] Documento persistido:")
    print(json.dumps(saved, indent=2, ensure_ascii=False, default=str))
    print("\n[Redis] Cache de mensagens recentes:")
    print(json.dumps([json.loads(item) for item in recent], indent=2, ensure_ascii=False))
    print("\nDemo concluida. Execute novamente para observar a idempotencia.")


if __name__ == "__main__":
    main()

