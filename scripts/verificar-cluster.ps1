$ErrorActionPreference = "Stop"

Write-Host "=== Namespaces ==="
kubectl get namespaces app,data,monitoring

Write-Host "`n=== Bancos ==="
kubectl get pods,statefulset,service,pvc -n data

Write-Host "`n=== Worker e HPA ==="
kubectl get deployment,pods,service,hpa -n app
kubectl describe hpa message-worker -n app

Write-Host "`n=== Monitoramento ==="
kubectl get pods,servicemonitor -n monitoring

Write-Host "`n=== Recursos consumidos ==="
kubectl top nodes
kubectl top pods -A

