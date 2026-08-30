#!/usr/bin/env python3
"""Convert Daemon Kenny dataset to Soup Alpaca format.

Reads JSONL dataset and outputs Soup-compatible Alpaca JSONL:
{instruction, input, output}
"""

import json
import sys
from pathlib import Path


def parse_json_value(value):
    """Parse JSON from string, handling code blocks."""
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str):
        raise ValueError("response is not JSON text")
    text = value.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:]) if len(lines) > 1 else text
        text = text.rsplit("```", 1)[0].strip()
    return json.loads(text)


def response_value(row):
    """Extract response dict from row."""
    for key in ("response", "kenny_response", "code_assist_response"):
        value = row.get(key)
        if value not in (None, ""):
            return parse_json_value(value)
    raise ValueError("row has no response column")


def row_mode(row, response):
    """Determine if this is code_assist or desktop_companion."""
    mode = str(row.get("mode", "desktop_companion"))
    if mode == "code_assist" or (isinstance(response, dict) and response.get("type") == "code_assist"):
        return "code_assist"
    return "desktop_companion"


def scenario_context(row):
    """Build scenario context string (simplified for Soup)."""
    mode = str(row.get("mode", "desktop_companion"))
    apm = int(row.get("apm", 0))
    idle_seconds = int(row.get("idle_seconds", 0))
    active_window = str(row.get("active_window", "desktop"))
    typing_content = str(row.get("typing_content", ""))
    screen_text = str(row.get("screen_text", ""))
    browser_url = str(row.get("browser_url", ""))
    memory_facts = str(row.get("memory_facts", ""))
    trigger_kind = str(row.get("trigger_kind", "user"))

    # For Soup, keep only essential fields; strip Kenny-specific details
    parts = []
    parts.append(f"Mode: {mode}")
    parts.append(f"APM: {apm}")
    parts.append(f"Idle: {idle_seconds}s")
    parts.append(f"Window: {active_window}")
    if screen_text:
        parts.append(f"Screen: {screen_text[:80]}")
    if browser_url:
        parts.append(f"Browser: {browser_url}")
    if memory_facts:
        parts.append(f"Memory: {memory_facts[:80]}")
    parts.append(f"Trigger: {trigger_kind}")
    if typing_content:
        parts.append(f"Typing: {typing_content[:50]}")

    return "\n".join(parts)


def convert_dataset(input_path, output_path):
    """Convert dataset to Soup Alpaca format."""
    inp = Path(input_path)
    if not inp.exists():
        raise FileNotFoundError(f"Dataset not found: {input_path}")

    # Read JSONL directly (no datasets library needed)
    valid_count = 0
    dropped = 0
    rows = []
    with open(inp, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
                rows.append(row)
            except json.JSONDecodeError as e:
                print(f"Skipping malformed line: {e}")
                dropped += 1

    print(f"Loaded {len(rows)} rows from dataset")

    with open(output_path, "w", encoding="utf-8") as f:
        for row in rows:
            try:
                response = response_value(row)
                mode = row_mode(row, response)
                ctx = scenario_context(row)

                # Extract the main dialogue text from response
                dialogue = response.get("dialogue", "")
                if not dialogue and isinstance(response, dict):
                    for k in ("dialogue", "response", "text"):
                        if k in response:
                            dialogue = str(response[k])
                            break
                    if not dialogue:
                        dialogue = str(response)

                # Truncate dialogue to reasonable length
                dialogue = dialogue[:200]

                # Build instruction from scenario context
                instruction = ctx

                # Soup Alpaca format: {instruction, input, output}
                alpaca_example = {
                    "instruction": instruction,
                    "input": "",  # empty for companion mode
                    "output": dialogue,
                }

                f.write(json.dumps(alpaca_example, ensure_ascii=False) + "\n")
                valid_count += 1
            except (ValueError, TypeError, json.JSONDecodeError) as e:
                dropped += 1
                if dropped <= 5:
                    print(f"Dropped row: {e}")

    print(f"Converted {valid_count} rows to Soup Alpaca format")
    print(f"Dropped {dropped} rows that failed conversion")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python convert_to_soup_alpaca.py <input_jsonl> <output_jsonl>")
        print("  input_jsonl: path to JSONL dataset (as in daemon.ipynb)")
        print("  output_jsonl: path for output Soup Alpaca JSONL")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]
    convert_dataset(input_path, output_path)