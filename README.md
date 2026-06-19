# Entrega do Guilherme - Mensageria, Processamento e Dados

Pacote da parte de **Guilherme Stein** no trabalho de Sistemas Distribuidos.

## Abrir no VS Code

Abra o arquivo `guilherme-mensageria.code-workspace`. Depois:

1. copie `.env.example` para `.env`;
2. abra `Terminal > Run Task`;
3. execute as tarefas numeradas de 1 a 4;
4. pressione `F5` e escolha `Demo local: processar uma mensagem`.

A demo local usa MongoDB e Redis reais em containers, mas simula o SNS para
que voce entenda o processamento sem precisar ligar o AWS Academy.

## O que esta implementado

- Worker em Python que:
  - consome mensagens do Amazon SQS com long polling;
  - valida o contrato da mensagem;
  - grava o historico no MongoDB;
  - mantem as 50 mensagens recentes no Redis;
  - publica a mensagem em `room:<roomId>` via Redis Pub/Sub;
  - publica o evento `message.created` no SNS;
  - remove a mensagem do SQS somente depois do processamento.
- Idempotencia por `messageId` no MongoDB.
- Lambda acionada pelo SNS e usando apenas biblioteca padrao.
- Manifests do worker, Service, HPA e ServiceMonitor.
- Values do Helm para MongoDB ReplicaSet, Redis e Prometheus/Grafana.
- Trecho Terraform para SQS, DLQ, SNS, Lambda e dashboard CloudWatch.
- Testes unitarios do processamento.
- Roteiro de demonstracao e explicacao para a equipe.

## Fluxo

```text
API -> SQS -> message-worker -> MongoDB
                            -> Redis cache + Pub/Sub -> pods da API -> WebSocket
                            -> SNS -> Lambda -> log de notificacao no CloudWatch
```

## Estrutura

```text
worker/                    codigo, Dockerfile e testes
lambda/                    funcao acionada pelo SNS
k8s/                       manifests e values Helm
terraform-snippets/        recursos para integrar ao Terraform do William
scripts/                   comandos auxiliares de verificacao
EXPLICACAO_PARA_O_GRUPO.md  resumo tecnico e fala sugerida
```

## 1. Testar o codigo

Na pasta `worker`:

```bash
python -m unittest discover -s tests -v
```

## 2. Criar a imagem

Troque o repositorio pelo utilizado pelo grupo:

```bash
docker build -t SEU_USUARIO/chat-message-worker:1.0.0 worker
docker push SEU_USUARIO/chat-message-worker:1.0.0
```

Depois altere `SEU_USUARIO` em `k8s/worker.yaml`.

## 3. Instalar os bancos

Adicione o repositorio:

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update
kubectl apply -f k8s/namespaces.yaml
```

Antes de instalar, troque todas as ocorrencias de `TROQUE_ESTA_SENHA`.

```bash
helm upgrade --install mongodb bitnami/mongodb \
  --namespace data \
  -f k8s/helm/mongodb-values.yaml

helm upgrade --install redis bitnami/redis \
  --namespace data \
  -f k8s/helm/redis-values.yaml
```

Verificacao:

```bash
kubectl get pods -n data
kubectl get statefulset -n data
kubectl exec -n data mongodb-0 -- mongosh \
  -u root -p TROQUE_ESTA_SENHA --authenticationDatabase admin \
  --eval "rs.status().members.map(m => ({name:m.name,state:m.stateStr}))"
```

## 4. Criar o Secret do worker

Copie o exemplo e troque senhas, URL da fila e ARN do topico:

```bash
kubectl apply -f k8s/worker-secret.example.yaml
```

O MongoDB usa tres hosts do StatefulSet e `replicaSet=rs0`:

```text
mongodb://chat:TROQUE_ESTA_SENHA@mongodb-0.mongodb-headless.data.svc.cluster.local:27017,mongodb-1.mongodb-headless.data.svc.cluster.local:27017,mongodb-2.mongodb-headless.data.svc.cluster.local:27017/chat?replicaSet=rs0&authSource=chat
```

Por padrao, o SDK AWS tenta usar o `LabInstanceProfile` da EC2. Se o IMDS nao
estiver acessivel de dentro dos pods, descomente no Secret as variaveis
`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` e `AWS_SESSION_TOKEN`. Elas sao
temporarias e precisam ser atualizadas quando o Learner Lab reiniciar.

## 5. Subir worker e HPA

```bash
kubectl apply -f k8s/worker.yaml
kubectl apply -f k8s/hpa.yaml
kubectl get pods,hpa -n app
kubectl logs -n app deployment/message-worker -f
```

O HPA usa CPU. Por isso `worker.yaml` define `resources.requests.cpu`; sem o
request, o Kubernetes nao consegue calcular a porcentagem de utilizacao.

## 6. Instalar observabilidade

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm upgrade --install monitoring prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  -f k8s/helm/monitoring-values.yaml

kubectl apply -f k8s/service-monitor.yaml
```

Acesso local ao Grafana:

```bash
kubectl port-forward -n monitoring service/monitoring-grafana 3000:80
```

Metricas do worker:

- `chat_worker_messages_received_total`
- `chat_worker_messages_processed_total`
- `chat_worker_processing_errors_total`
- `chat_worker_processing_seconds`
- `chat_worker_last_success_unixtime`

## 7. Integrar recursos AWS

O arquivo `terraform-snippets/messaging.tf` deve ser adaptado ao Terraform
principal pelo William. Ele cria:

- fila `chat-messages`;
- DLQ `chat-messages-dlq`;
- topico `chat-notifications`;
- Lambda com `LabRole`;
- assinatura SNS -> Lambda;
- permissao de invocacao;
- dashboard CloudWatch.

Para gerar o ZIP da Lambda no PowerShell:

```powershell
Compress-Archive -Path .\lambda\handler.py -DestinationPath .\lambda\notifier.zip -Force
```

## 8. Contratos de integracao

Mensagem que a API deve publicar no SQS:

```json
{
  "messageId": "uuid",
  "roomId": "uuid",
  "userId": "uuid",
  "username": "guilherme",
  "content": "ola",
  "timestamp": "2026-06-19T18:00:00Z"
}
```

Evento que o worker publica no SNS:

```json
{
  "eventType": "message.created",
  "roomId": "uuid",
  "messageId": "uuid",
  "username": "guilherme",
  "preview": "ola",
  "timestamp": "2026-06-19T18:00:00Z"
}
```

Payload publicado no Redis e salvo no MongoDB:

```json
{
  "id": "uuid",
  "roomId": "uuid",
  "userId": "uuid",
  "username": "guilherme",
  "content": "ola",
  "createdAt": "2026-06-19T18:00:00Z"
}
```

## Decisao consciente sobre a Lambda

A Lambda nao acessa o DNS interno do k3s. Para consultar o Redis do cluster ela
precisaria de rede privada/VPC e uma forma segura de expor o servico, o que
aumenta muito o escopo no AWS Academy. Neste MVP, a Lambda recebe o evento real
do SNS e grava no CloudWatch uma notificacao simulada, alternativa expressamente
permitida no contrato da API.
