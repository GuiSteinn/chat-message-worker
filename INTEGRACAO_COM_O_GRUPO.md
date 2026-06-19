# Integracao da parte do Guilherme com o grupo

## Status que voce pode mandar no grupo

> Pessoal, minha parte de mensageria e dados ja esta implementada. O worker
> consome o contrato definido para o SQS, valida a mensagem, persiste no
> MongoDB, atualiza o cache e publica no Redis Pub/Sub. Depois ele publica o
> evento de notificacao no SNS, que aciona a Lambda. Tambem deixei os values do
> MongoDB ReplicaSet e Redis, o Deployment/HPA do worker e a configuracao de
> Prometheus/Grafana e CloudWatch. Para integrar, preciso do William a URL real
> do SQS, o ARN do SNS, acesso ao cluster e a definicao do repositorio da
> imagem. Do Andrei preciso apenas que a API publique exatamente o JSON do
> contrato e assine o canal Redis `room:<roomId>`.

## O que esta pronto

- Codigo do `message-worker`.
- Validacao da mensagem recebida.
- Persistencia idempotente no MongoDB.
- Cache das ultimas 50 mensagens no Redis.
- Redis Pub/Sub por sala.
- Publicacao do evento no SNS.
- Lambda acionada por SNS.
- Dockerfile do worker.
- Deployment, Service, Secret de exemplo e HPA.
- MongoDB ReplicaSet e Redis via Helm.
- Metricas Prometheus e ServiceMonitor.
- Dashboard CloudWatch em Terraform.
- Testes unitarios.

## Integracao com Andrei - frontend/API/WebSocket

### O que voce precisa receber dele

Nada de codigo interno. A API precisa publicar no SQS este formato:

```json
{
  "messageId": "uuid",
  "roomId": "uuid",
  "userId": "uuid",
  "username": "string",
  "content": "string",
  "timestamp": "ISO 8601"
}
```

### O que voce entrega para ele

Depois do processamento, o worker publica no canal:

```text
room:<roomId>
```

O payload e:

```json
{
  "id": "uuid",
  "roomId": "uuid",
  "userId": "uuid",
  "username": "string",
  "content": "string",
  "createdAt": "ISO 8601"
}
```

A API do Andrei deve manter uma assinatura Redis e encaminhar esse payload aos
WebSockets conectados na sala.

### Teste de contrato com Andrei

1. Andrei envia uma mensagem pela API.
2. A profundidade do SQS aumenta.
3. O worker registra `Mensagem processada`.
4. O documento aparece no MongoDB.
5. A API recebe o evento Redis.
6. A mensagem aparece no navegador.

## Integracao com William Wollert - AWS, Terraform e cluster

### O que voce precisa receber dele

- `SQS_QUEUE_URL`;
- `SNS_TOPIC_ARN`;
- kubeconfig do cluster;
- nome do registry e da imagem Docker;
- confirmacao de que os nodes usam `LabInstanceProfile`;
- outputs ou credenciais temporarias caso o instance profile nao funcione.

### O que voce entrega para ele

- `terraform-snippets/messaging.tf`;
- `lambda/handler.py`;
- imagem Docker do worker;
- pasta `k8s/`;
- nomes e valores das variaveis de ambiente.

### Divisao sem conflito

William provisiona e faz o deploy. Guilherme e dono do codigo e das
configuracoes funcionais dos componentes. William pode incorporar os arquivos
ao Terraform e ao pipeline sem reescrever a logica do worker.

## Integracao com Wiliam M. Weber - artigo

Envie para ele:

- o fluxo SQS -> Worker -> MongoDB/Redis -> SNS -> Lambda;
- justificativa de cada componente;
- print do ReplicaSet;
- print do HPA aumentando pods;
- dashboard do Grafana;
- dashboard CloudWatch;
- logs da Lambda;
- explicacao de idempotencia e retry.

Frase tecnica para o artigo:

> Como o Amazon SQS Standard possui semantica de entrega pelo menos uma vez, o
> worker usa o `messageId` como chave unica no MongoDB e realiza persistencia
> idempotente. A mensagem so e removida da fila depois da conclusao das etapas
> de persistencia e publicacao.

## Ordem recomendada da integracao

1. William cria SQS, SNS e Lambda e entrega URL/ARN.
2. Guilherme instala MongoDB e Redis.
3. Guilherme publica a imagem Docker e aplica worker/HPA.
4. Andrei configura a API com SQS e Redis.
5. Todos testam uma mensagem ponta a ponta.
6. O grupo executa carga e coleta prints.

## Definicao de pronto

Sua parte pode ser considerada integrada quando:

- o worker aparece `Running`;
- uma mensagem sai do SQS;
- o MongoDB possui o documento;
- o Redis possui a mensagem recente;
- dois pods da API recebem o Pub/Sub;
- o SNS mostra publicacao;
- a Lambda possui uma invocacao no CloudWatch;
- o HPA mostra metricas de CPU;
- o Prometheus coleta `/metrics`.

