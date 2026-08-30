# Observability and chatbot load checks

Prometheus scrapes `/metrics`. Import `daemon-dashboard.json` into Grafana and
load `alerts.yml` into Prometheus Alertmanager rules. Panels use bounded,
low-cardinality labels (`request_type`, `provider`, and `tool`).

Run the offline repeatable path check:

```powershell
py scripts/load_test_chatbot.py --iterations 10 --concurrency 8
```

The default harness uses no QApplication, QThread, provider, MCP socket, or
persistence. An injected transport can be used by tests or an explicitly
opted-in environment smoke test. Keep iterations and concurrency bounded
(1–32 concurrency) to preserve predictable CI and soak-test resource usage.
