import json

with open('fine_tuning/soup/batch_00000_alpaca.jsonl', 'r') as f:
    lines = f.readlines()
    # Check a few more entries to understand prompt format
    for i in [0, 1, 5, 10, 15, 20]:
        if i < len(lines):
            entry = json.loads(lines[i])
            inst = entry.get('instruction', '')[:200]
            out = entry.get('output', '')[:100]
            print(f"Entry {i}:")
            print(f"  Instruction (first 200 chars): {inst}...")
            print(f"  Output (first 100 chars): {out}...")
            print()