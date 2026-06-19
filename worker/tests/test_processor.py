import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models import IncomingMessage
from app.processor import MessageProcessor


class FakeCollection:
    def __init__(self):
        self.documents = {}

    def update_one(self, query, update, upsert=False):
        message_id = query["id"]
        if message_id not in self.documents and upsert:
            self.documents[message_id] = deepcopy(update["$setOnInsert"])
        for path, value in update.get("$set", {}).items():
            target = self.documents[message_id]
            parts = path.split(".")
            for part in parts[:-1]:
                target = target.setdefault(part, {})
            target[parts[-1]] = value

    def find_one(self, query, projection=None):
        document = self.documents.get(query["id"])
        return deepcopy(document) if document else None


class FakePipeline:
    def __init__(self, redis):
        self.redis = redis
        self.commands = []

    def lrem(self, key, count, value):
        self.commands.append(("lrem", key, count, value))
        return self

    def lpush(self, key, value):
        self.commands.append(("lpush", key, value))
        return self

    def ltrim(self, key, start, end):
        self.commands.append(("ltrim", key, start, end))
        return self

    def publish(self, channel, value):
        self.commands.append(("publish", channel, value))
        return self

    def execute(self):
        self.redis.executions.append(self.commands)


class FakeRedis:
    def __init__(self):
        self.executions = []

    def pipeline(self, transaction=True):
        return FakePipeline(self)


class FakeSns:
    def __init__(self):
        self.publications = []

    def publish(self, **kwargs):
        self.publications.append(kwargs)


def valid_message():
    return IncomingMessage.from_dict(
        {
            "messageId": "m-1",
            "roomId": "r-1",
            "userId": "u-1",
            "username": "Guilherme",
            "content": "Ola, sistemas distribuidos!",
            "timestamp": "2026-06-19T18:00:00Z",
        }
    )


class ProcessorTests(unittest.TestCase):
    def setUp(self):
        self.collection = FakeCollection()
        self.redis = FakeRedis()
        self.sns = FakeSns()
        self.processor = MessageProcessor(
            self.collection,
            self.redis,
            self.sns,
            "arn:aws:sns:us-east-1:123:chat-notifications",
        )

    def test_processes_contract_and_publishes(self):
        result = self.processor.process(valid_message())

        self.assertEqual(result["id"], "m-1")
        self.assertEqual(len(self.redis.executions), 1)
        self.assertEqual(len(self.sns.publications), 1)
        event = json.loads(self.sns.publications[0]["Message"])
        self.assertEqual(event["eventType"], "message.created")
        self.assertEqual(event["messageId"], "m-1")
        self.assertTrue(
            self.collection.documents["m-1"]["delivery"]["redisPublished"]
        )
        self.assertTrue(
            self.collection.documents["m-1"]["delivery"]["snsPublished"]
        )

    def test_retry_does_not_repeat_completed_outputs(self):
        self.processor.process(valid_message())
        self.processor.process(valid_message())

        self.assertEqual(len(self.collection.documents), 1)
        self.assertEqual(len(self.redis.executions), 1)
        self.assertEqual(len(self.sns.publications), 1)

    def test_rejects_missing_fields(self):
        with self.assertRaises(ValueError):
            IncomingMessage.from_dict({"messageId": "m-1"})

    def test_rejects_invalid_timestamp(self):
        payload = {
            "messageId": "m-1",
            "roomId": "r-1",
            "userId": "u-1",
            "username": "Guilherme",
            "content": "Oi",
            "timestamp": "ontem",
        }
        with self.assertRaises(ValueError):
            IncomingMessage.from_dict(payload)


if __name__ == "__main__":
    unittest.main()

