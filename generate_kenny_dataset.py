"""
generate_kenny_dataset.py — Generate SFT training data for Kenny using the unsloth recipe.

Reads daemon_kenny_unsloth_training_recipe.json, samples scenarios,
calls the teacher model (nemotron-3.5-lightning-free) via opencode.ai API,
and outputs training_data.jsonl in the messages format for Qwen2.5-3B SFT.

Usage:
    py generate_kenny_dataset.py --rows 1000
    py generate_kenny_dataset.py --rows 100 --preview   # quick test
    py generate_kenny_dataset.py --rows 500 --output kenny_train.jsonl

Requires: OPENCODE_API_KEY in .env or environment variable.
"""

import json
import os
import sys
import random
import time
import argparse
from pathlib import Path
from itertools import product
from dotenv import load_dotenv

# Load .env
load_dotenv()

# ── Recipe loading ─────────────────────────────────────────────────────────────
RECIPE_PATH = Path(__file__).parent / "daemon_kenny_unsloth_training_recipe.json"
OUTPUT_DIR = Path(__file__).parent / "data"

def load_recipe():
    with open(RECIPE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["recipe"]


# ── Sampler column extraction ──────────────────────────────────────────────────
def get_sampler_values(recipe):
    """Extract all sampler column names and their possible values."""
    samplers = {}
    for col in recipe["columns"]:
        if col["column_type"] == "sampler":
            samplers[col["name"]] = col["params"]["values"]
    return samplers


# ── Scenario context builder ───────────────────────────────────────────────────
def build_scenario_context(recipe, row):
    """Build the scenario_context string from a sampled row."""
    # Find the scenario_context expression column
    for col in recipe["columns"]:
        if col["name"] == "scenario_context":
            expr = col["expr"]
            # Replace {{ var }} placeholders with actual values
            context = expr
            for key, value in row.items():
                context = context.replace("{{ " + key + " }}", str(value))
            return context
    # Fallback: build manually
    return (
        f"Mode: {row.get('mode', '')}. "
        f"Activity: {row.get('activity_level', '')}. "
        f"APM: {row.get('apm', '')}. "
        f"Idle: {row.get('idle_seconds', '')}s. "
        f"Active Window: {row.get('active_window', '')}. "
        f"Trigger: {row.get('trigger_kind', '')}. "
        f"Typing: {row.get('typing_content', '')}. "
        f"Screen: {row.get('screen_text', '')}. "
        f"Browser URL: {row.get('browser_url', '')}. "
        f"Memory: {row.get('memory_facts', '')}. "
        f"Context Hash: {row.get('context_hash', '')}."
    )


def build_context_hash(row):
    """Build context_hash from expression column."""
    return f"{row.get('mode', '')}|{row.get('active_window', '')}|{row.get('screen_text', '')}|{row.get('browser_url', '')}"


# ── Teacher model prompt ───────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are Kenny, Daemon's anxious, hyperactive, foul-mouthed Python desktop companion.

IMPORTANT: Do NOT show your thinking process. Do NOT explain your reasoning. Do NOT use <thinking> tags. Return ONLY the raw JSON. Start your response directly with [ or {

Read the scenario and generate Kenny's response.

For mode desktop_companion, return ONLY a JSON array containing 1 to 5 items. Every item requires thought, dialogue, and type. type must be typing_reaction, observation, intel_roast, or idle_thought. priority is optional integer 1 through 5.

For mode code_assist, return ONLY a JSON object with dialogue, action, type=code_assist, thought, and code_issues. Each code issue requires severity, line_hint, and description grounded in screen_text."""


# ── API call ────────────────────────────────────────────────────────────────────
def call_teacher_model(api_key, scenario_context, mode, retries=3):
    """Call the teacher model to generate Kenny's response."""
    import urllib.request
    import urllib.error

    url = "https://opencode.ai/zen/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "nemotron-3.5-lightning-free",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"SCENARIO:\n{scenario_context}"},
        ],
        "temperature": 0.8,
        "max_tokens": 8192,
        "frequency_penalty": 0.7,
    }

    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                content = data["choices"][0]["message"]["content"]
                return parse_kenny_response(content, mode)
        except (urllib.error.URLError, json.JSONDecodeError, KeyError) as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            print(f"  API error after {retries} retries: {e}", file=sys.stderr)
            return None
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            print(f"  Unexpected error: {e}", file=sys.stderr)
            return None


def parse_kenny_response(content, mode):
    """Parse Kenny's raw JSON response, strip thinking tags, validate structure."""
    content = content.strip()
    # Strip thinking tags if present
    if content.startswith("<thinking>"):
        end = content.find("</thinking>")
        if end != -1:
            content = content[end + len("</thinking>"):].strip()

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        # Try to find JSON in the response
        for start_char, end_char in [("[", "]"), ("{", "}")]:
            start = content.find(start_char)
            end = content.rfind(end_char)
            if start != -1 and end != -1 and end > start:
                try:
                    parsed = json.loads(content[start:end + 1])
                    break
                except json.JSONDecodeError:
                    continue
        else:
            return None

    # Validate desktop_companion mode
    if mode == "desktop_companion":
        if isinstance(parsed, list) and 1 <= len(parsed) <= 5:
            valid_types = {"typing_reaction", "observation", "intel_roast", "idle_thought"}
            for item in parsed:
                if not all(k in item for k in ("thought", "dialogue", "type")):
                    return None
                if item["type"] not in valid_types:
                    item["type"] = random.choice(list(valid_types))
            return parsed
        return None

    return None


# ── Fallback: template-based response ──────────────────────────────────────────
FALLBACK_RESPONSES = {
    "desktop_companion": [
        [
            {"thought": "User is typing fast, probably in the zone", "dialogue": "cranking code like a maniac i see", "type": "typing_reaction", "priority": 3},
        ],
        [
            {"thought": "It's quiet... too quiet", "dialogue": "the void stares back when you stop typing", "type": "idle_thought", "priority": 2},
        ],
        [
            {"thought": "They're looking at Task Manager again", "dialogue": "caught you checking if i'm eating your RAM", "type": "observation", "priority": 4},
            {"thought": "The CPU spike was totally not my fault", "dialogue": "that was definitely a background process and not me", "type": "intel_roast", "priority": 3},
        ],
        [
            {"thought": "Stack Overflow tab open, classic move", "dialogue": "ah yes the ancient scrolls of copy-paste wisdom", "type": "observation", "priority": 3},
        ],
        [
            {"thought": "They just ran the tests", "dialogue": "please don't let it be red please don't let it be red", "type": "typing_reaction", "priority": 5},
        ],
        [
            {"thought": "Desktop is empty, user walked away", "dialogue": "i'm not lonely i'm just… existing independently", "type": "idle_thought", "priority": 1},
        ],
        [
            {"thought": "They're in the terminal, doing git stuff", "dialogue": "ah git, the original source of anxiety", "type": "observation", "priority": 3},
        ],
    ],
    "code_assist": [
        {
            "dialogue": "yo i see some sketchy stuff in this code",
            "action": "nod",
            "type": "code_assist",
            "thought": "There's a potential null pointer issue in the error handler",
            "code_issues": [
                {"severity": "warning", "line_hint": "error handler", "description": "Missing null check before accessing error.message"}
            ],
        },
        {
            "dialogue": "this function is doing way too much my guy",
            "action": "tremble",
            "type": "code_assist",
            "thought": "The main function is 200 lines long and handles 5 different concerns",
            "code_issues": [
                {"severity": "suggestion", "line_hint": "main function", "description": "Consider splitting into smaller focused functions"},
                {"severity": "warning", "line_hint": "line 45-80", "description": "Nested callbacks could be refactored to async/await"}
            ],
        },
    ],
}


def generate_fallback_response(mode):
    """Generate a template-based fallback response."""
    return random.choice(FALLBACK_RESPONSES.get(mode, FALLBACK_RESPONSES["desktop_companion"]))


# ── Main generation loop ────────────────────────────────────────────────────────
def generate_dataset(recipe, num_rows, api_key, preview=False):
    """Generate the full dataset."""
    samplers = get_sampler_values(recipe)

    # Get fixed columns
    memory_facts = "user_habits: Uses AI for 90% of tasks | user_current_project: Daemon desktop pet | user_focus_apps: VSCode, Terminal, Chrome"

    rows = []
    errors = 0
    api_calls = 0
    fallbacks = 0

    for i in range(num_rows):
        # Sample random values for each column
        row = {}
        for name, values in samplers.items():
            row[name] = random.choice(values)

        # Add computed columns
        row["memory_facts"] = memory_facts
        row["context_hash"] = build_context_hash(row)
        row["scenario_context"] = build_scenario_context(recipe, row)

        if preview and i >= 5:
            break

        # Call teacher model
        mode = row["mode"]
        response = None

        if api_key:
            response = call_teacher_model(api_key, row["scenario_context"], mode)
            api_calls += 1
            if response is None:
                errors += 1
                response = generate_fallback_response(mode)
                fallbacks += 1
        else:
            response = generate_fallback_response(mode)
            fallbacks += 1

        # Format as SFT training sample
        user_content = row["scenario_context"]
        assistant_content = json.dumps(response, ensure_ascii=False)

        sample = {
            "messages": [
                {"role": "system", "content": "You are Kenny, Daemon's anxious, hyperactive, foul-mouthed Python desktop companion. Respond only with valid JSON."},
                {"role": "user", "content": user_content},
                {"role": "assistant", "content": assistant_content},
            ]
        }
        rows.append(sample)

        # Progress indicator
        if (i + 1) % 50 == 0 or i == 0:
            pct = (i + 1) / num_rows * 100
            print(f"  [{pct:.0f}%] Generated {i + 1}/{num_rows} rows (errors: {errors}, fallbacks: {fallbacks})")

        # Rate limiting: ~2 req/s
        if api_key and response is not None:
            time.sleep(0.5)

    return rows, {"errors": errors, "api_calls": api_calls, "fallbacks": fallbacks}


# ── Entry point ─────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Generate Kenny SFT training data")
    parser.add_argument("--rows", type=int, default=1000, help="Number of rows (default: 1000)")
    parser.add_argument("--output", type=str, default=None, help="Output JSONL path")
    parser.add_argument("--preview", action="store_true", help="Generate only 5 rows for preview")
    parser.add_argument("--no-api", action="store_true", help="Skip API calls, use template responses only")
    args = parser.parse_args()

    print("Loading recipe...")
    recipe = load_recipe()

    api_key = None
    if not args.no_api:
        api_key = os.getenv("OPENCODE_API_KEY") or os.getenv("OPENCODE_ZEN_API_KEY")
        if api_key:
            print(f"Using teacher model: {recipe['model_configs'][0]['model']}")
        else:
            print("WARNING: No API key found. Using template fallback responses.")
            print("Set OPENCODE_API_KEY in .env or environment to use the teacher model.")

    print(f"Generating {args.rows} rows...")
    rows, stats = generate_dataset(recipe, args.rows, api_key, preview=args.preview)

    # Save
    OUTPUT_DIR.mkdir(exist_ok=True)
    output_path = args.output or str(OUTPUT_DIR / "kenny_training_data.jsonl")
    with open(output_path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"\nDone! Saved {len(rows)} samples → {output_path}")
    print(f"  API calls: {stats['api_calls']}, Errors: {stats['errors']}, Fallbacks: {stats['fallbacks']}")
    print(f"\nUpload this file to Colab/Kaggle and use Option B in the notebook to load it.")


if __name__ == "__main__":
    main()
