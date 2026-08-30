import json

with open('fine_tuning/soup/batch_00000_alpaca.jsonl', 'r') as f:
    lines = f.readlines()

alpaca_data = []
for line in lines:
    entry = json.loads(line)
    # For Alpaca SFT format:
    # - instruction: the full context/metadata (this is what the model conditions on)
    # - input: typically empty or additional context (here it's always empty)
    # - output: the desired response from the model
    alpaca_entry = {
        "instruction": entry.get('instruction', ''),
        "input": entry.get('input', ''),
        "output": entry.get('output', '')
    }
    alpaca_data.append(alpaca_entry)

# Write Alpaca-format JSONL
with open('fine_tuning/soup/batch_00000_alpaca_clean.jsonl', 'w') as f:
    for entry in alpaca_data:
        f.write(json.dumps(entry) + '\n')

print(f'Created {len(alpaca_data)} Alpaca-format entries')
print(f'\nFirst 3 entries:')

for i, entry in enumerate(alpaca_data[:3]):
    print(f"\n--- Entry {i} ---")
    print(f"instruction: {entry['instruction'][:100]}...")
    print(f"input: '{entry['input']}'")
    print(f"output: {entry['output'][:100]}...")