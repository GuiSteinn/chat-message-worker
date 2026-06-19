# Como explicar a parte do Guilherme

## Resumo em uma frase

Minha parte recebe a mensagem de forma assincrona, garante a persistencia,
distribui o evento em tempo real e dispara a notificacao sem bloquear a API.

## O que acontece quando alguem envia uma mensagem

1. A API recebe a mensagem pelo WebSocket e coloca um JSON no SQS.
2. Um pod do `message-worker` busca a mensagem usando long polling.
3. O worker valida os campos definidos no contrato.
4. O worker faz um `upsert` no MongoDB usando `messageId` como chave unica.
5. Ele atualiza a lista `room:<roomId>:recent` no Redis.
6. Ele publica o JSON no canal `room:<roomId>`.
7. Todos os pods da API inscritos nesse canal recebem o evento e o enviam aos
   clientes conectados por WebSocket.
8. O worker publica um evento menor no SNS.
9. O SNS aciona a Lambda, que registra uma notificacao simulada no CloudWatch.
10. Somente quando tudo termina o worker apaga a mensagem do SQS.

## Por que usar cada tecnologia

- **SQS:** desacopla a API do processamento e permite retry quando algo falha.
- **Worker:** concentra a persistencia e pode escalar sem replicar essa logica na API.
- **MongoDB ReplicaSet:** mantem o historico com replicacao e tolerancia a falhas.
- **Redis:** cacheia mensagens recentes e resolve a comunicacao entre varios pods.
- **SNS:** distribui o evento de notificacao sem acoplar o worker a uma funcao especifica.
- **Lambda:** executa sob demanda, sem manter outro servidor.
- **HPA:** aumenta ou reduz a quantidade de workers conforme a CPU.
- **Prometheus/Grafana:** mostram metricas do cluster e da aplicacao.
- **CloudWatch:** mostra fila SQS, invocacoes/erros da Lambda e logs.

## Garantias e limites

O SQS Standard trabalha com entrega **pelo menos uma vez**, portanto uma
mensagem pode reaparecer. Para evitar duplicar o historico, o MongoDB possui
indice unico em `id` e o worker usa `upsert`.

Redis Pub/Sub e SNS tambem podem repetir um evento se o pod cair exatamente
entre publicar e registrar o sucesso. Os consumidores devem tratar
`messageId` como identificador de deduplicacao. Isso e normal em sistemas
distribuidos: preferimos uma eventual repeticao a perder uma mensagem.

O worker so chama `DeleteMessage` no SQS depois de completar as etapas. Se
falhar, o visibility timeout expira e a mensagem volta para processamento. A
DLQ recebe mensagens que falham repetidamente.

## Fala sugerida para a apresentacao

> Eu implementei a parte assincrona do chat. A API nao grava diretamente no
> banco; ela envia para o SQS e responde rapidamente. O worker consome a fila,
> persiste no MongoDB ReplicaSet, atualiza o cache e publica no Redis Pub/Sub.
> O Redis e essencial porque temos varios pods da API: ele faz todos receberem
> a mesma mensagem, independentemente de qual pod mantem o WebSocket do
> usuario. Depois o worker publica um evento no SNS, que aciona a Lambda de
> notificacao. Como o SQS pode entregar mais de uma vez, usei o messageId como
> chave unica para tornar a persistencia idempotente. O worker tambem expoe
> metricas para o Prometheus e escala por HPA.

## Demonstracao ideal

Abra quatro terminais:

```bash
# 1. Worker processando
kubectl logs -n app deployment/message-worker -f

# 2. Pods e HPA
kubectl get pods,hpa -n app -w

# 3. Estado da fila
aws sqs get-queue-attributes \
  --queue-url "$SQS_QUEUE_URL" \
  --attribute-names ApproximateNumberOfMessagesVisible ApproximateNumberOfMessagesNotVisible

# 4. Historico salvo
kubectl exec -n data mongodb-0 -- mongosh \
  -u root -p TROQUE_ESTA_SENHA --authenticationDatabase admin \
  --eval "db.getSiblingDB('chat').messages.find().sort({createdAt:-1}).limit(5)"
```

No navegador, deixe o Grafana aberto no dashboard de pods e o CloudWatch no
dashboard `chat-distribuido`.

## Perguntas que podem fazer

**Por que a API nao grava direto no MongoDB?**  
Para desacoplar o recebimento do processamento. Se o banco ficar lento, as
mensagens aguardam na fila e a API continua disponivel.

**Por que MongoDB ReplicaSet com tres pods?**  
Para demonstrar banco distribuido: existe um primario e replicas, permitindo
replicacao e eleicao de um novo primario em falhas.

**Redis Pub/Sub garante persistencia?**  
Nao. A persistencia e responsabilidade do MongoDB. O Redis serve para entrega
em tempo real e cache.

**O HPA mede o tamanho da fila?**  
Nesta versao mede CPU, que e mais simples e usa o metrics-server do k3s.
Escalar diretamente pelo tamanho da fila exigiria KEDA, uma melhoria futura.

**Por que a Lambda apenas simula?**  
Porque ela esta fora do cluster e nao resolve o DNS interno do Redis. O
contrato permite log/simulacao; o gatilho SNS -> Lambda continua sendo real.

**O que acontece se o worker cair?**  
A mensagem nao e apagada. Depois do visibility timeout ela reaparece no SQS e
outro pod tenta novamente.

