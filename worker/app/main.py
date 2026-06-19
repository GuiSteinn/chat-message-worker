from __future__ import annotations

import json
import logging
import os
import signal
import time
from typing import Any

import boto3
import redis
from prometheus_client import start_http_server
from pymongo import ASCENDING, DESCENDING, MongoClient

from .metrics import (
    LAST_SUCCESS,
    MESSAGES_PROCESSED,
    MESSAGES_RECEIVED,
    PROCESSING_ERRORS,
    PROCESSING_SECONDS,
)
from .models import IncomingMessage
from .processor import MessageProcessor


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
LOGGER = logging.getLogger("message-worker")
RUNNING = True


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Variavel obrigatoria ausente: {name}")
    return value


def stop(_signum: int, _frame: Any) -> None:
    global RUNNING
    LOGGER.info("Encerramento solicitado; finalizando polling")
    RUNNING = False


def build_processor() -> tuple[MessageProcessor, Any, str]:
    region = os.getenv("AWS_REGION", "us-east-1")
    queue_url = required_env("SQS_QUEUE_URL")
    topic_arn = required_env("SNS_TOPIC_ARN")

    mongo_client = MongoClient(
        required_env("MONGODB_URI"),
        serverSelectionTimeoutMS=5000,
        appname="chat-message-worker",
    )
    mongo_client.admin.command("ping")
    collection = mongo_client["chat"]["messages"]
    collection.create_index([("id", ASCENDING)], unique=True)
    collection.create_index([("roomId", ASCENDING), ("createdAt", DESCENDING)])

    redis_client = redis.Redis.from_url(
        required_env("REDIS_URL"),
        decode_responses=True,
        socket_connect_timeout=5,
        health_check_interval=30,
    )
    redis_client.ping()

    sqs_client = boto3.client("sqs", region_name=region)
    sns_client = boto3.client("sns", region_name=region)
    processor = MessageProcessor(
        collection=collection,
        redis_client=redis_client,
        sns_client=sns_client,
        sns_topic_arn=topic_arn,
        recent_limit=int(os.getenv("RECENT_MESSAGES_LIMIT", "50")),
    )
    return processor, sqs_client, queue_url


def run() -> None:
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    start_http_server(int(os.getenv("METRICS_PORT", "8000")))

    processor, sqs, queue_url = build_processor()
    wait_seconds = int(os.getenv("SQS_WAIT_TIME_SECONDS", "20"))
    visibility_timeout = int(os.getenv("SQS_VISIBILITY_TIMEOUT", "60"))
    LOGGER.info("Worker iniciado; aguardando mensagens em %s", queue_url)

    while RUNNING:
        try:
            response = sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=10,
                WaitTimeSeconds=wait_seconds,
                VisibilityTimeout=visibility_timeout,
                AttributeNames=["ApproximateReceiveCount"],
            )
            for sqs_message in response.get("Messages", []):
                MESSAGES_RECEIVED.inc()
                message_id = sqs_message.get("MessageId", "desconhecido")
                receive_count = (
                    sqs_message.get("Attributes", {}).get(
                        "ApproximateReceiveCount",
                        "1",
                    )
                )
                try:
                    with PROCESSING_SECONDS.time():
                        payload = json.loads(sqs_message["Body"])
                        incoming = IncomingMessage.from_dict(payload)
                        processor.process(incoming)
                        sqs.delete_message(
                            QueueUrl=queue_url,
                            ReceiptHandle=sqs_message["ReceiptHandle"],
                        )
                    MESSAGES_PROCESSED.inc()
                    LAST_SUCCESS.set_to_current_time()
                    LOGGER.info(
                        "Mensagem processada",
                        extra={
                            "message_id": incoming.message_id,
                            "sqs_message_id": message_id,
                        },
                    )
                except Exception as exc:
                    PROCESSING_ERRORS.labels(type(exc).__name__).inc()
                    LOGGER.exception(
                        "Falha ao processar SQS messageId=%s tentativa=%s",
                        message_id,
                        receive_count,
                    )
        except Exception:
            PROCESSING_ERRORS.labels("PollingError").inc()
            LOGGER.exception("Falha no polling do SQS; nova tentativa em 5s")
            time.sleep(5)


if __name__ == "__main__":
    run()

