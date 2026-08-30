import json
import re

# Read original dataset
with open('fine_tuning/soup/batch_00000_alpaca.jsonl', 'r') as f:
    lines = f.readlines()

alpaca_data = []
for line in lines:
    entry = json.loads(line)
    instruction = entry.get('instruction', '')
    output = entry.get('output', '')
    
    # Extract the actual query from instruction metadata
    # The instruction format is: "Mode: xxx\nAPM: yyy\n..." followed by the actual prompt
    # We need to extract just the meaningful prompt part
    
    # Remove the Mode/APM metadata prefix and get the actual task
    # The prompt part is after all the metadata lines
    lines_split = instruction.split('\n')
    
    # Find where the actual prompt starts (look for content that's not metadata)
    prompt = None
    for i, line in enumerate(lines_split):
        # Skip metadata lines (Mode, APM, Idle, Window, etc.)
        if line.startswith('Mode:') or line.startswith('APM:') or line.startswith('Idle:') \
           or line.startswith('Window:') or line.startswith('Screen:') or line.startswith('Browser:') \
           or line.startswith('Memory:') or line.startswith('Trigger:'):
            continue
        else:
            # This is likely the actual prompt
            prompt = instruction[i:] if i == 0 else '\n'.join(lines_split[i:])
            break
    
    # If no prompt found in metadata, use the full instruction
    if prompt is None:
        prompt = instruction.strip()
    
    # Clean up: remove any trailing metadata that might have been included
    # The prompt should be the actual user query
    
    # For Alpaca format: instruction = the task, input = optional context, output = response
    alpaca_entry = {
        "instruction": prompt.strip(),
        "input": "",  # No additional input in this dataset
        "output": output.strip()
    }
    alpaca_data.append(alpaca_entry)

# Write Alpaca-format JSONL
with open('fine_tuning/soup/batch_00000_alpaca_clean.jsonl', 'w') as f:
    for entry in alpaca_data:
        f.write(json.dumps(entry) + '\n')

print(f'Created {len(alpaca_data)} Alpaca-format entries')
print(f'\nFirst entry:')
print(json.dumps(alpaca_data[0], indent=2))