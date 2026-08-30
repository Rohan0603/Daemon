import json
with open('fine_tuning/soup/batch_00000_alpaca.jsonl', 'r') as f:
    lines = f.readlines()
    print(f'Total lines: {len(lines)}')
    # Check first entry
    first = json.loads(lines[0])
    print(f'First entry keys: {list(first.keys())}')
    print(f'First instruction: {first["instruction"][:80]}...')
    print(f'First input: "{first["input"]}"')
    print(f'First output: {first["output"][:80]}...')
    # Check if all entries have same structure
    keys_set = set()
    for i, line in enumerate(lines[:5]):
        entry = json.loads(line)
        keys_set.update(entry.keys())
    print(f'All entry keys across first 5: {keys_set}')