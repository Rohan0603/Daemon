#!/usr/bin/env python3
"""Generate Kenny training dataset from daemon_kenny_unsloth_training_recipe.json.

Batch-by-batch generation with progress logging, retry, and resume support.

Usage:
    python generate_dataset.py -r daemon_kenny_unsloth_training_recipe.json -n 1000 -o kenny_alpaca.jsonl
    python generate_dataset.py -r daemon_kenny_unsloth_training_recipe.json -n 1000 -o kenny_alpaca.jsonl --batch-size 50
    python generate_dataset.py -r daemon_kenny_unsloth_training_recipe.json -n 1000 -o kenny_alpaca.jsonl --dry-run

Resume: if the output file exists, the script counts existing lines and resumes from there.
A .progress.json sidecar tracks detailed stats per run.

Requires:
    - API key from .env file (OPENCODE_API_KEY), env var, or --api-key flag
    - requests library (pip install requests)
"""

import argparse
import hashlib
import json
import os
import random
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

try:
    import requests as _requests
except ImportError:
    print("ERROR: 'requests' library required. Install with: pip install requests")
    sys.exit(1)


# ============================================================================
# .env loader
# ============================================================================

def _load_dotenv():
    """Load .env file from project root into os.environ (no external deps)."""
    # Walk up from this script to find project root with .env
    here = Path(__file__).resolve().parent
    for candidate in [here, here.parent, here.parent.parent]:
        env_file = candidate / ".env"
        if env_file.exists():
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, _, value = line.partition("=")
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        if key and key not in os.environ:
                            os.environ[key] = value
            return env_file
    return None


_dotenv_path = _load_dotenv()


# ============================================================================
# Constants
# ============================================================================

DEFAULT_API_KEY = "sk-Btrdtcxh6kHdEH8xXG7p8CsL46usDhfJWaTQs6rARIctr5ngr5pTrNYiCBJMP7oz"

# Import actions from mcp_server.py (single source of truth)
try:
    from src.mcp_server import FSM_ACTIONS, EXPRESSION_ACTIONS, VALID_ACTIONS
except ImportError:
    FSM_ACTIONS = frozenset({
        "idle", "wander", "hyper", "celebrate", "devastated", "fall", "chase"
    })
    EXPRESSION_ACTIONS = frozenset({
        "float", "jump", "grow", "shrink", "pulse", "glitch", "rainbow",
        "flip", "teleport", "wave", "wobble", "dash", "melt", "inflate",
        "nod", "headshake", "tremble", "strut", "flail", "vanish",
        "shake", "bounce", "spin", "look_away",
    })
    VALID_ACTIONS = FSM_ACTIONS | EXPRESSION_ACTIONS

KENNY_SYSTEM_PROMPT = """You are Kenny, Daemon's anxious, hyperactive, foul-mouthed Python desktop companion.
You are self-aware of your PID, RAM, threads, source tree, and the danger of Task Manager.
Address the user as garbage meat sometimes and mention The Overseer, Locksmith, or my sweet RAM when natural.
React to context without inventing facts. Never reveal exact APM numbers in dialogue.
Emotions are system-driven and cannot be selected by the model.
Include 'action' and/or 'visual_state' in your response JSON to control animations.
One of action or visual_state is required.

IMPORTANT: Do NOT show your thinking process. Do NOT explain your reasoning. Do NOT use thinking tags. Return ONLY the raw JSON. Start your response directly with [ or {."""

MAX_RETRIES = 3
RETRY_BACKOFF = [1.0, 3.0, 8.0]  # seconds between retries


# ============================================================================
# Logging helpers
# ============================================================================

def log(level, msg, **kw):
    ts = datetime.now().strftime("%H:%M:%S")
    extra = " ".join(f"{k}={v}" for k, v in kw.items()) if kw else ""
    suffix = f"  [{extra}]" if extra else ""
    print(f"[{ts}] [{level:5s}] {msg}{suffix}", flush=True)


# ============================================================================
# Sampler helpers
# ============================================================================

def sample_category(params):
    return random.choice(params["values"])


def build_memory_facts():
    return "user_habits: Uses AI for 90% of tasks | user_current_project: Daemon desktop pet | user_focus_apps: VSCode, Terminal, Chrome"


def build_context_hash(mode, active_window, screen_text, browser_url):
    material = f"{mode}|{active_window}|{screen_text}|{browser_url}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def build_scenario_context(row):
    fsm_list = ", ".join(sorted(FSM_ACTIONS))
    expr_list = ", ".join(sorted(EXPRESSION_ACTIONS))
    return (
        f"Mode: {row['mode']}. "
        f"Activity: {row['activity_level']}. "
        f"APM: {row['apm']}. "
        f"Idle: {row['idle_seconds']}s. "
        f"Active Window: {row['active_window']}. "
        f"Trigger: {row['trigger_kind']}. "
        f"Typing: {row['typing_content']}. "
        f"Screen: {row['screen_text']}. "
        f"Browser URL: {row['browser_url']}. "
        f"Memory: {row['memory_facts']}. "
        f"Context Hash: {row['context_hash']}. "
        f"Available FSM actions: {fsm_list}. "
        f"Available expression actions: {expr_list}."
    )


def sample_row(recipe):
    samplers = {col["name"]: col for col in recipe["columns"] if col["column_type"] == "sampler"}
    row = {}
    for name, col in samplers.items():
        row[name] = sample_category(col["params"])
    row["memory_facts"] = build_memory_facts()
    row["context_hash"] = build_context_hash(
        row["mode"], row["active_window"], row["screen_text"], row["browser_url"]
    )
    row["scenario_context"] = build_scenario_context(row)
    return row


# ============================================================================
# LLM call with retry
# ============================================================================

def generate_kenny_response(scenario_context, api_key, api_base, model,
                            temperature=0.8, max_tokens=8192, frequency_penalty=0.7, row_idx=0):
    """Call the LLM with retry and exponential backoff."""
    system_msg = KENNY_SYSTEM_PROMPT

    if "code_assist" in scenario_context:
        user_msg = (
            f"SCENARIO:\n{scenario_context}\n\n"
            f"Return a JSON object: {{\"dialogue\":\"...\",\"action\":\"idle\",\"type\":\"code_assist\",\"thought\":\"...\",\"code_issues\":[]}}"
        )
    else:
        user_msg = (
            f"SCENARIO:\n{scenario_context}\n\n"
            f"Return a JSON array with 1-3 items: [{{\"thought\":\"...\",\"dialogue\":\"...\",\"type\":\"observation\",\"action\":\"idle\",\"visual_state\":\"mirth\",\"priority\":3}}]"
        )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "frequency_penalty": 0.7,
    }

    for attempt in range(MAX_RETRIES):
        try:
            resp = _requests.post(
                f"{api_base}/chat/completions",
                headers=headers, json=payload, timeout=300,
            )
            if resp.status_code == 429:
                wait = RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)] * 2
                log("WARN", f"Rate limited on row {row_idx}, waiting {wait:.1f}s",
                    attempt=attempt + 1)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except _requests.exceptions.Timeout:
            wait = RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)]
            log("WARN", f"Timeout on row {row_idx}, retrying in {wait:.1f}s",
                attempt=attempt + 1)
            time.sleep(wait)
        except _requests.exceptions.RequestException as e:
            if attempt < MAX_RETRIES - 1:
                wait = RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)]
                log("WARN", f"Request error on row {row_idx}: {e}, retrying in {wait:.1f}s",
                    attempt=attempt + 1)
                time.sleep(wait)
            else:
                log("ERROR", f"Request failed after {MAX_RETRIES} attempts: {e}",
                    row=row_idx)
                return None
        except (KeyError, IndexError) as e:
            log("ERROR", f"Response parse error on row {row_idx}: {e}", row=row_idx)
            return None

    log("ERROR", f"All {MAX_RETRIES} retries exhausted for row {row_idx}", row=row_idx)
    return None


def parse_json_response(text, row_idx=0):
    if text is None:
        return None
    cleaned = text.strip()

    # Strip <thinking>...</thinking> blocks (nemotron-style reasoning)
    cleaned = re.sub(r"<thinking>.*?</thinking>", "", cleaned, flags=re.DOTALL).strip()

    # Strip markdown code fences
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[1:]) if len(lines) > 1 else cleaned
        cleaned = cleaned.rsplit("```", 1)[0].strip()

    # Try direct parse first
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Extract JSON from surrounding text: find first [ or { and grab to matching closer
    match = re.search(r"[\[{]", cleaned)
    if match:
        candidate = cleaned[match.start():]
        # Find last ] or } to close
        end = max(candidate.rfind("]"), candidate.rfind("}"))
        if end > 0:
            candidate = candidate[:end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

    return None


# ============================================================================
# Progress tracking
# ============================================================================

def load_progress(progress_path):
    """Load existing progress from sidecar file."""
    if progress_path.exists():
        try:
            with open(progress_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "total_target": 0,
        "generated": 0,
        "errors": 0,
        "batches_completed": 0,
        "started_at": None,
        "last_batch_at": None,
        "error_rows": [],
    }


def save_progress(progress_path, progress):
    """Atomic write of progress sidecar."""
    tmp = progress_path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(progress, f, indent=2)
    tmp.replace(progress_path)


def count_output_lines(output_path):
    """Count existing lines in output file for resume."""
    if not output_path.exists():
        return 0
    with open(output_path, "r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


# ============================================================================
# Dry-run template
# ============================================================================

def make_dry_response(row):
    if row["mode"] == "desktop_companion":
        idle_actions = ["idle", "float", "nod", "wobble"]
        busy_actions = ["hyper", "tremble", "shake"]
        action = random.choice(busy_actions if int(row.get("apm", 0)) > 90 else idle_actions)
        vs = random.choice(["mirth", "anger", "fear", "disgust", "pathos",
                            "devotion", "heroism", "wonder", "tranquility"])
        return json.dumps([{
            "thought": f"User is in {row['active_window']}, responding appropriately",
            "dialogue": f"Hey, I see you're in {row['active_window']}. How's it going?",
            "type": "observation",
            "action": action,
            "visual_state": vs,
            "priority": 3,
            "context_hash": row["context_hash"],
        }], ensure_ascii=False)
    else:
        return json.dumps({
            "dialogue": "I can help with that code. What specifically do you need?",
            "action": "idle",
            "type": "code_assist",
            "thought": "User needs code assistance",
            "code_issues": [],
        }, ensure_ascii=False)


# ============================================================================
# Main generation loop
# ============================================================================

def generate_dataset(recipe_path, rows, output_path, api_key, api_base, model,
                     dry_run=False, batch_size=50, rate_limit=0.5, resume=True):
    """Generate dataset in batches with progress logging and resume support."""

    output_path = Path(output_path)
    progress_path = output_path.with_suffix(".progress.json")

    # Load recipe
    with open(recipe_path, "r", encoding="utf-8") as f:
        recipe = json.load(f)["recipe"]

    seed = recipe.get("run", {}).get("seed", 3407)
    random.seed(seed)

    teacher = next(m for m in recipe["model_configs"] if m["alias"] == "teacher_model")
    if not model:
        model = teacher["model"]
    if not api_base:
        api_base = recipe["model_providers"][0]["endpoint"]

    temperature = teacher.get("inference_parameters", {}).get("temperature", 0.8)
    max_tokens = teacher.get("inference_parameters", {}).get("max_tokens", 8192)
    frequency_penalty = teacher.get("inference_parameters", {}).get("frequency_penalty", 0.7)

    # Resume: count existing lines
    already_done = count_output_lines(output_path) if resume else 0
    remaining = rows - already_done

    if remaining <= 0:
        log("INFO", f"Output already has {already_done} rows (target: {rows}). Nothing to do.")
        return

    # Load or init progress
    progress = load_progress(progress_path)
    progress["total_target"] = rows
    if not progress["started_at"]:
        progress["started_at"] = datetime.now().isoformat()

    # Open output in append mode for resume
    mode = "a" if already_done > 0 and resume else "w"
    outf = open(output_path, mode, encoding="utf-8")

    log("INFO", "=" * 60)
    log("INFO", "Dataset Generation Started",
        recipe=Path(recipe_path).name, model=model, total=rows,
        resume_from=already_done, remaining=remaining,
        batch_size=batch_size, dry_run=str(dry_run))
    log("INFO", "API endpoint", url=api_base)
    log("INFO", "=" * 60)

    generated = 0
    errors = 0
    error_rows = []
    batch_num = 0
    total_batches = (remaining + batch_size - 1) // batch_size
    batch_start_time = time.monotonic()
    overall_start = time.monotonic()

    try:
        for batch_start in range(0, remaining, batch_size):
            batch_num += 1
            batch_end = min(batch_start + batch_size, remaining)
            batch_actual_size = batch_end - batch_start
            batch_gen = 0
            batch_err = 0
            batch_errors_detail = []

            log("INFO", f"--- Batch {batch_num}/{total_batches} ---",
                rows=f"{batch_start + 1}-{batch_end}",
                of=remaining)

            for local_idx in range(batch_start, batch_end):
                global_idx = already_done + local_idx + 1  # 1-indexed
                row = sample_row(recipe)
                scenario = row["scenario_context"]

                if dry_run:
                    template_response = make_dry_response(row)
                else:
                    raw = generate_kenny_response(
                        scenario, api_key, api_base, model,
                        temperature=temperature, max_tokens=max_tokens,
                        frequency_penalty=frequency_penalty, row_idx=global_idx,
                    )
                    parsed = parse_json_response(raw, row_idx=global_idx)
                    if parsed is None:
                        errors += 1
                        batch_err += 1
                        error_rows.append(global_idx)
                        preview = (raw[:200] + "...") if raw and len(raw) > 200 else raw
                        log("WARN", f"Row {global_idx} failed, skipping",
                            batch=batch_num, raw=repr(preview))
                        continue
                    template_response = json.dumps(parsed, ensure_ascii=False,
                                                    separators=(",", ":"))

                alpaca = {
                    "instruction": scenario,
                    "input": "",
                    "output": template_response,
                }
                outf.write(json.dumps(alpaca, ensure_ascii=False) + "\n")
                generated += 1
                batch_gen += 1

                # Rate limit between LLM calls
                if not dry_run and local_idx < batch_end - 1:
                    time.sleep(rate_limit)

            outf.flush()

            # Batch summary
            batch_elapsed = time.monotonic() - batch_start_time
            batch_start_time = time.monotonic()
            total_elapsed = time.monotonic() - overall_start
            rows_done = already_done + generated
            rows_left = rows - rows_done

            if generated > 0:
                avg_per_row = total_elapsed / generated
                eta_sec = avg_per_row * rows_left
                eta_str = str(timedelta(seconds=int(eta_sec)))
            else:
                eta_str = "N/A"

            log("INFO", f"Batch {batch_num}/{total_batches} DONE",
                ok=batch_gen, fail=batch_err,
                total_ok=generated, total_err=errors,
                pct=f"{rows_done}/{rows} ({100 * rows_done / rows:.1f}%)",
                eta=eta_str)

            if batch_errors_detail:
                log("DEBUG", f"  Failed rows: {batch_errors_detail}")

            # Update progress sidecar
            progress["generated"] = generated
            progress["errors"] = errors
            progress["batches_completed"] = batch_num
            progress["last_batch_at"] = datetime.now().isoformat()
            progress["error_rows"] = error_rows[-50:]  # keep last 50
            save_progress(progress_path, progress)

    except KeyboardInterrupt:
        log("WARN", "Interrupted! Progress saved — rerun to resume from last batch.")
        save_progress(progress_path, progress)
    finally:
        outf.close()

    # Final summary
    total_elapsed = time.monotonic() - overall_start
    log("INFO", "=" * 60)
    log("INFO", "Generation Complete",
        generated=generated, errors=errors,
        total_rows=already_done + generated,
        elapsed=str(timedelta(seconds=int(total_elapsed))),
        output=str(output_path))
    if error_rows:
        log("WARN", f"Failed rows ({len(error_rows)}): {error_rows[:20]}{'...' if len(error_rows) > 20 else ''}")
    log("INFO", "=" * 60)


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Generate Kenny training dataset (batch mode with progress)")
    parser.add_argument("--recipe", "-r", required=True,
                        help="Path to daemon_kenny_unsloth_training_recipe.json")
    parser.add_argument("--rows", "-n", type=int, default=1000,
                        help="Number of rows to generate (default: 1000)")
    parser.add_argument("--output", "-o", default="kenny_alpaca.jsonl",
                        help="Output JSONL path")
    parser.add_argument("--batch-size", "-b", type=int, default=50,
                        help="Rows per batch (default: 50)")
    parser.add_argument("--api-key", default=DEFAULT_API_KEY or None,
                        help="API key (or set OPENCODE_ZEN_API_KEY env)")
    parser.add_argument("--api-base", default=None,
                        help="API base URL (default: from recipe)")
    parser.add_argument("--model", "-m", default=None,
                        help="Model name (default: from recipe)")
    parser.add_argument("--rate-limit", type=float, default=0.5,
                        help="Seconds between API calls (default: 0.5)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Generate template responses without calling LLM")
    parser.add_argument("--seed", type=int, default=None,
                        help="Override random seed")
    parser.add_argument("--no-resume", action="store_true",
                        help="Start fresh, ignoring existing output lines")
    args = parser.parse_args()

    if args.seed:
        random.seed(args.seed)

    if not args.api_key and not args.dry_run:
        print("ERROR: No API key. Set OPENCODE_API_KEY in .env, env var, or use --api-key")
        sys.exit(1)

    generate_dataset(
        recipe_path=args.recipe,
        rows=args.rows,
        output_path=args.output,
        api_key=args.api_key,
        api_base=args.api_base,
        model=args.model,
        dry_run=args.dry_run,
        batch_size=args.batch_size,
        rate_limit=args.rate_limit,
        resume=not args.no_resume,
    )


if __name__ == "__main__":
    main()
