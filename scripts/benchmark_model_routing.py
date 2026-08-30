"""Repeatable provider benchmark for Daemon's OpenCode and Ollama HTTP APIs.

The benchmark talks to provider APIs directly, so it does not start Qt,
modify Daemon configuration, or invoke tools.  Tool adherence is measured from
the provider response when a case declares expected tool names.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import ctypes
import json
import os
import statistics
import time
import tracemalloc
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import requests


DEFAULT_CASES = [
    {"name": "json_dialogue", "prompt": "Reply with JSON: {\"dialogue\":\"hello\",\"action\":\"idle\"}."},
    {
        "name": "tool_adherence",
        "prompt": "Call the change_visual_state tool with action idle, then reply with JSON.",
        "expected_tools": ["change_visual_state"],
    },
]


def _rss_bytes() -> int:
    """Return current process RSS without adding a dependency."""
    if os.name == "nt":
        class Counters(ctypes.Structure):
            _fields_ = [("cb", ctypes.c_ulong), ("page_fault_count", ctypes.c_ulong),
                        ("peak_working_set", ctypes.c_size_t), ("working_set", ctypes.c_size_t)]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        try:
            ctypes.windll.psapi.GetProcessMemoryInfo(
                ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb
            )
        except (AttributeError, OSError):
            return 0
        return int(counters.working_set)
    try:
        import resource
        value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return int(value * (1024 if value < 1024 * 1024 else 1))
    except (ImportError, AttributeError):
        return 0


def _json_valid(text: str) -> bool:
    try:
        value = json.loads(text)
    except (TypeError, ValueError):
        return False
    return isinstance(value, (dict, list))


def _usage(data: dict[str, Any]) -> dict[str, int]:
    usage = data.get("usage") or (data if "prompt_eval_count" in data else {})
    values = {
        "prompt_tokens": int(usage.get("prompt_tokens", usage.get("prompt_eval_count", 0)) or 0),
        "completion_tokens": int(usage.get("completion_tokens", usage.get("eval_count", 0)) or 0),
        "total_tokens": int(usage.get("total_tokens", 0) or 0),
    }
    if not values["total_tokens"]:
        values["total_tokens"] = values["prompt_tokens"] + values["completion_tokens"]
    return values


def _extract_text(provider: str, data: dict[str, Any]) -> str:
    if provider == "ollama":
        return str((data.get("message") or {}).get("content") or data.get("response") or "")
    for part in data.get("parts", []):
        if isinstance(part, dict) and part.get("type") == "text":
            return str(part.get("text") or "")
    return str(data.get("text") or data.get("content") or "")


def _extract_tools(data: dict[str, Any]) -> list[str]:
    found: list[str] = []
    blocks = list(data.get("tool_calls") or [])
    blocks.extend((data.get("message") or {}).get("tool_calls") or [])
    for part in data.get("parts", []):
        if isinstance(part, dict) and part.get("type") in {"tool", "tool_call", "tool-call", "tool_use"}:
            blocks.append(part)
    for block in blocks:
        function = block.get("function", block) if isinstance(block, dict) else {}
        name = function.get("name") if isinstance(function, dict) else None
        if name:
            found.append(str(name))
    return found


@dataclass
class Sample:
    provider: str
    model: str
    case: str
    run: int
    ok: bool
    latency_ms: float
    ttfe_ms: float
    json_valid: bool
    tool_adherent: bool | None
    tool_calls: list[str]
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cpu_time_ms: float
    rss_delta_mb: float
    error: str = ""


def _request(provider: str, url: str, model: str, prompt: str, timeout: float) -> tuple[dict[str, Any], str, float, float]:
    started = time.perf_counter()
    if provider == "ollama":
        response = requests.post(
            url.rstrip("/") + "/api/chat",
            json={"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False},
            timeout=timeout,
        )
    else:
        session = requests.post(url.rstrip("/") + "/session", json={}, timeout=timeout)
        session.raise_for_status()
        sid = session.json().get("id") or session.json().get("session_id")
        if not sid:
            raise RuntimeError("OpenCode session response had no id")
        try:
            response = requests.post(
                url.rstrip("/") + f"/session/{sid}/message",
                json={"parts": [{"type": "text", "text": prompt}]},
                timeout=timeout,
            )
            response_received = time.perf_counter()
        finally:
            try:
                requests.delete(url.rstrip("/") + f"/session/{sid}", timeout=timeout)
            except requests.RequestException:
                pass
    if provider == "ollama":
        response_received = time.perf_counter()
    ttfe = (response_received - started) * 1000
    response.raise_for_status()
    return response.json(), response.text, ttfe, (response_received - started) * 1000


def run_sample(provider: str, url: str, model: str, case: dict[str, Any], run: int, timeout: float) -> Sample:
    before_rss = _rss_bytes()
    before_cpu = time.process_time()
    try:
        data, raw, ttfe, latency = _request(provider, url, model, case["prompt"], timeout)
        text = _extract_text(provider, data)
        tools = _extract_tools(data)
        expected = set(case.get("expected_tools", []))
        adherence = bool(expected.intersection(tools)) if expected else None
        usage = _usage(data)
        return Sample(provider, model, case["name"], run, True, latency, ttfe,
                      _json_valid(text), adherence, tools, **usage,
                      cpu_time_ms=(time.process_time() - before_cpu) * 1000,
                      rss_delta_mb=(_rss_bytes() - before_rss) / 1024 / 1024)
    except Exception as exc:
        return Sample(provider, model, case["name"], run, False, 0, 0, False, None, [],
                      0, 0, 0, (time.process_time() - before_cpu) * 1000,
                      (_rss_bytes() - before_rss) / 1024 / 1024, f"{type(exc).__name__}: {exc}")


def summarize(samples: list[Sample]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for provider in sorted({sample.provider for sample in samples}):
        rows = [sample for sample in samples if sample.provider == provider]
        successful = [sample for sample in rows if sample.ok]
        values = lambda name: [getattr(sample, name) for sample in successful]
        adherence = [sample.tool_adherent for sample in successful if sample.tool_adherent is not None]
        def percentile(name: str, fraction: float) -> float | None:
            values_list = sorted(values(name))
            if not values_list:
                return None
            return values_list[min(len(values_list) - 1, round((len(values_list) - 1) * fraction))]

        result[provider] = {
            "samples": len(rows), "success_rate": len(successful) / len(rows) if rows else 0,
            "latency_ms": statistics.fmean(values("latency_ms")) if successful else None,
            "ttfe_ms": statistics.fmean(values("ttfe_ms")) if successful else None,
            "latency_p95_ms": percentile("latency_ms", 0.95),
            "ttfe_p95_ms": percentile("ttfe_ms", 0.95),
            "json_valid_rate": statistics.fmean(values("json_valid")) if successful else 0,
            "tool_adherence_rate": statistics.fmean(adherence) if adherence else None,
            "tokens": {"prompt": sum(values("prompt_tokens")), "completion": sum(values("completion_tokens")),
                       "total": sum(values("total_tokens"))},
            "resources": {"cpu_time_ms": sum(values("cpu_time_ms")),
                          "rss_delta_mb_max": max(values("rss_delta_mb"), default=0)},
        }
    return result


def load_cases(path: str | None) -> list[dict[str, Any]]:
    if not path:
        return DEFAULT_CASES
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, list) or not all(isinstance(case, dict) for case in value):
        raise ValueError("cases file must contain a JSON array of objects")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("opencode", "ollama", "both"), default="both")
    parser.add_argument("--opencode-url", default="http://127.0.0.1:4096")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--model", default="", help="Model label (Ollama model; OpenCode label is for reporting).")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--cases", help="JSON file containing [{name,prompt,expected_tools?}, ...]")
    parser.add_argument("--output", default="benchmark-results.json")
    args = parser.parse_args()
    if args.runs < 1 or args.concurrency < 1:
        parser.error("--runs and --concurrency must be positive")
    providers = ("opencode", "ollama") if args.provider == "both" else (args.provider,)
    cases = load_cases(args.cases)
    tracemalloc.start()
    jobs = [(provider, case, run) for provider in providers for run in range(1, args.runs + 1) for case in cases]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [pool.submit(run_sample, provider, args.ollama_url if provider == "ollama" else args.opencode_url,
                                args.model, case, run, args.timeout) for provider, case, run in jobs]
        samples = [future.result() for future in futures]
    payload = {"config": vars(args), "samples": [asdict(sample) for sample in samples],
               "summary": summarize(samples), "peak_tracemalloc_mb": tracemalloc.get_traced_memory()[1] / 1024 / 1024}
    Path(args.output).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2))
    return 0 if all(sample.ok for sample in samples) else 1


if __name__ == "__main__":
    raise SystemExit(main())
