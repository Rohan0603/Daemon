import json
with open('fine_tuning/soup/batch_00000_alpaca_clean.jsonl', 'r') as f:
    lines = f.readlines()
    entry = json.loads(lines[0])
    print("Sample entry structure:")
    print(f"  Keys: {list(entry.keys())}")
    print(f"  instruction starts with: {entry['instruction'][:50]}...")
    print(f"  input: '{entry['input']}' (always empty)")
    print(f"  output starts with: {entry['output'][:50]}...")