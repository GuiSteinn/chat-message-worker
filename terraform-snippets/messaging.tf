# Este arquivo e um trecho para integrar ao Terraform principal.
# Ele pressupoe que data.aws_iam_role.lab_role ja existe em data.tf e que o
# provider hashicorp/archive foi declarado em required_providers.

data "archive_file" "chat_notifier" {
  type        = "zip"
  source_file = "${path.module}/../lambda/handler.py"
  output_path = "${path.module}/../lambda/notifier.zip"
}

resource "aws_sqs_queue" "chat_messages_dlq" {
  name                      = "chat-messages-dlq"
  message_retention_seconds = 1209600
}

resource "aws_sqs_queue" "chat_messages" {
  name                       = "chat-messages"
  visibility_timeout_seconds = 60
  receive_wait_time_seconds  = 20
  message_retention_seconds  = 345600

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.chat_messages_dlq.arn
    maxReceiveCount     = 5
  })
}

resource "aws_sns_topic" "chat_notifications" {
  name = "chat-notifications"
}

resource "aws_lambda_function" "chat_notifier" {
  function_name    = "chat-notifier"
  role             = data.aws_iam_role.lab_role.arn
  runtime          = "python3.12"
  handler          = "handler.lambda_handler"
  filename         = data.archive_file.chat_notifier.output_path
  source_code_hash = data.archive_file.chat_notifier.output_base64sha256
  timeout          = 10
  memory_size      = 128

  environment {
    variables = {
      NOTIFICATION_MODE = "cloudwatch-log"
    }
  }
}

resource "aws_sns_topic_subscription" "chat_notifier" {
  topic_arn = aws_sns_topic.chat_notifications.arn
  protocol  = "lambda"
  endpoint  = aws_lambda_function.chat_notifier.arn
}

resource "aws_lambda_permission" "allow_sns" {
  statement_id  = "AllowSNSInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.chat_notifier.function_name
  principal     = "sns.amazonaws.com"
  source_arn    = aws_sns_topic.chat_notifications.arn
}

resource "aws_cloudwatch_dashboard" "chat" {
  dashboard_name = "chat-distribuido"

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        x = 0
        y = 0
        width = 12
        height = 6
        properties = {
          title = "SQS - mensagens visiveis e em processamento"
          region = "us-east-1"
          stat = "Average"
          period = 60
          metrics = [
            ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", aws_sqs_queue.chat_messages.name],
            [".", "ApproximateNumberOfMessagesNotVisible", ".", "."]
          ]
        }
      },
      {
        type = "metric"
        x = 12
        y = 0
        width = 12
        height = 6
        properties = {
          title = "Lambda - invocacoes e erros"
          region = "us-east-1"
          stat = "Sum"
          period = 60
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", aws_lambda_function.chat_notifier.function_name],
            [".", "Errors", ".", "."]
          ]
        }
      }
    ]
  })
}

output "chat_sqs_queue_url" {
  value = aws_sqs_queue.chat_messages.url
}

output "chat_sns_topic_arn" {
  value = aws_sns_topic.chat_notifications.arn
}
