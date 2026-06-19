from prometheus_client import Counter, Gauge, Histogram


MESSAGES_RECEIVED = Counter(
    "chat_worker_messages_received_total",
    "Quantidade de mensagens recebidas do SQS.",
)
MESSAGES_PROCESSED = Counter(
    "chat_worker_messages_processed_total",
    "Quantidade de mensagens processadas com sucesso.",
)
PROCESSING_ERRORS = Counter(
    "chat_worker_processing_errors_total",
    "Quantidade de erros de processamento.",
    ("error_type",),
)
PROCESSING_SECONDS = Histogram(
    "chat_worker_processing_seconds",
    "Tempo de processamento de cada mensagem.",
)
LAST_SUCCESS = Gauge(
    "chat_worker_last_success_unixtime",
    "Timestamp Unix do ultimo processamento bem-sucedido.",
)

