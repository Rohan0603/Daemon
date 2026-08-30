# Model routing benchmark and deployment runtime

`scripts/benchmark_model_routing.py` compares the existing OpenCode (`:4096`)
and Ollama (`:11434`) HTTP paths without changing provider or Daemon config.
It runs repeatable JSON cases and writes one JSON result file containing per
sample and aggregate **latency**, **TTFE** (time until the HTTP response is
available; both providers are non-streaming), **tool adherence**, **JSON
validity**, token counts, CPU time, RSS delta, concurrency, and errors.

## Running

From PowerShell:

```powershell
py scripts\benchmark_model_routing.py --provider ollama --model llama3.2-1b-q8:latest --runs 5 --output data\benchmark-ollama.json
py scripts\benchmark_model_routing.py --provider opencode --runs 5 --output data\benchmark-opencode.json
py scripts\benchmark_model_routing.py --provider both --runs 3 --concurrency 2 --output data\benchmark-routing.json
```

The default cases include structured JSON dialogue and a `change_visual_state`
tool-adherence probe. Custom cases are a JSON array:

```json
[{"name":"smoke","prompt":"Return JSON with dialogue and action."},
 {"name":"tool","prompt":"Call change_visual_state with idle.","expected_tools":["change_visual_state"]}]
```

Provider failures are retained in `samples`; the command exits non-zero if any
sample fails. Run the same cases, model, quantization, concurrency, and host
conditions when comparing results. Token fields are provider-reported where
available (Ollama `prompt_eval_count`/`eval_count`); OpenCode may report zero.

## Runtime recommendations

These recommendations follow Daemon's current implementation: OpenCode uses
short-lived `POST /session` → `/message` → `DELETE /session` bursts, while
Ollama uses `/api/chat`, `keep_alive=10m`, `num_predict=1024`, and a background
warm-up. Both paths can execute MCP tools, but OpenCode normally executes its
registered tools server-side; Ollama loops tool calls through the local MCP
client with a ten-iteration cap.

| Deployment | Recommendation |
|---|---|
| Windows source run | Use `py`, keep providers on loopback, verify `ffmpeg` separately for TTS, and benchmark after model warm-up. Keep concurrency at 1 for the desktop UI. |
| WSL | Run Ollama and benchmark inside the same WSL distribution when possible; loopback and GPU visibility differ across WSL/Windows boundaries. Use the Windows OpenCode endpoint only after measuring its network overhead. |
| Docker GPU | Expose Ollama's HTTP port only to the Daemon host, pass through NVIDIA GPU with the NVIDIA Container Toolkit, and benchmark container-to-host latency. Avoid publishing MCP port beyond loopback. |
| Docker CPU | Prefer a small quantized model, cap concurrency at 1–2, and expect materially higher TTFE. Reserve host CPU for Qt/APM/TTS; do not run high-concurrency inference beside the pet. |
| GPU selection | Prefer GPU offload when available; confirm with provider diagnostics and compare TTFE plus RSS, not tokens alone. Keep enough VRAM for model weights and context. |
| CPU selection | Use the smallest model that meets JSON/tool adherence targets. Quantization reduces memory pressure but can reduce adherence; verify with this benchmark. |
| Quantization | Compare Q4/Q5/Q8 variants at identical prompts and warm state. Record model tag in `--model`; never infer quality from latency alone. |
| Concurrency | Benchmark 1 first. Increase only until p95 latency or JSON/tool adherence regresses; production Daemon should normally remain serial to protect UI responsiveness. |
| Resources | Watch `rss_delta_mb`, CPU time, provider token counts, and host thermals. Use `--runs 5+` and discard first cold-start sample when making a capacity decision. |

Benchmark output is evidence, not a default configuration change. Keep
provider URLs, model selection, timeouts, and quantization in existing
configuration/UI paths.
