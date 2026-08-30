"""
generate_dataset.py — Create synthetic SFT training data for Qwen2.5-3B fine-tuning.

Usage:
    python generate_dataset.py --task "summarization" --domain "customer support" --num-samples 100
    
Output: training_data.jsonl (upload to Colab/Kaggle)

Requirements: None (uses only stdlib). For higher quality, use an LLM API:
    pip install openai  # then use generate_with_llm.py
"""

import json
import argparse
import random
import sys
from pathlib import Path

# ── Sample task templates ──────────────────────────────────────────────────────
# Replace these with your actual use case

TASK_TEMPLATES = {
    "summarization": {
        "instructions": [
            "Summarize the following text in 2-3 sentences.",
            "Provide a brief summary of this passage.",
            "Condense the following content into a short summary.",
            "Write a concise summary of the text below.",
        ],
        "inputs": [
            "The quarterly report shows a 15% increase in revenue driven primarily by the new product launch in Q2. Customer acquisition costs decreased by 8% while retention rates improved to 92%. The team expanded to 45 engineers, with 3 new feature teams focused on AI integration.",
            "Our hospital served 1,200 patients last month with an average wait time of 23 minutes. Emergency department utilization was at 78% capacity. We successfully reduced readmission rates by implementing the new follow-up protocol, saving an estimated $340,000 in operational costs.",
            "The machine learning model achieved 94.2% accuracy on the test set after fine-tuning with the augmented dataset. Training took 6 hours on 4 A100 GPUs. The model shows particular strength in handling edge cases that previously caused 15% of prediction errors.",
            "Climate change projections indicate a 2.5°C temperature rise by 2100 under current emission trajectories. Sea levels could rise by 0.5 meters, affecting 150 million people in coastal regions. Renewable energy adoption needs to triple to meet Paris Agreement targets.",
            "The software update includes 47 bug fixes, 12 new features, and 8 performance improvements. Critical security patches address three CVEs rated high severity. Migration from v2.x to v3.x requires database schema updates and API endpoint changes.",
        ],
    },
    "classification": {
        "instructions": [
            "Classify the following text into one of the categories.",
            "What category does this text belong to?",
            "Assign the appropriate label to this content.",
            "Determine the classification of the following text.",
        ],
        "inputs": [
            "URGENT: Server latency spiked to 500ms across all regions starting at 14:32 UTC. Database connection pool exhausted. Awaiting immediate response.",
            "Hi team, just wanted to share that the new feature demo went great today! Stakeholders loved the progress. Keep up the excellent work!",
            "Please review the attached pull request #342 which adds rate limiting to the API endpoints. Uses token bucket algorithm with configurable burst limits.",
            "The patient presents with persistent cough, fever of 101.3F, and mild shortness of breath for 3 days. No known allergies. Recommend chest X-ray and CBC.",
            "Invoice #INV-2024-0892 is 45 days overdue. Total amount: $12,450. Previous reminder sent on Jan 15. Please process payment immediately.",
        ],
        "labels": ["urgent", "positive", "technical", "medical", "financial"],
    },
    "chat": {
        "instructions": [
            "Help me with the following question.",
            "I need assistance with this.",
            "Can you explain this to me?",
            "What do you think about this?",
        ],
        "inputs": [
            "How do I set up a Python virtual environment?",
            "What's the difference between TCP and UDP?",
            "Can you explain how transformers work in machine learning?",
            "How should I approach debugging a memory leak in a Node.js application?",
            "What are the best practices for designing a REST API?",
        ],
    },
    "custom": {
        "instructions": [],  # Fill with your own
        "inputs": [],
    },
}

OUTPUT_TEMPLATE = {
    "messages": [
        {"role": "user", "content": ""},
        {"role": "assistant", "content": ""},
    ]
}


def generate_simple_task(task_type: str, num_samples: int, output_path: str):
    """Generate synthetic training data from templates (no LLM needed)."""
    templates = TASK_TEMPLATES.get(task_type, TASK_TEMPLATES["chat"])
    
    if not templates["instructions"]:
        print(f"Error: No templates for task type '{task_type}'")
        print(f"Available types: {', '.join(TASK_TEMPLATES.keys())}")
        print("Edit this script to add custom templates, or use --llm flag.")
        sys.exit(1)
    
    samples = []
    for i in range(num_samples):
        instruction = random.choice(templates["instructions"])
        input_text = random.choice(templates["inputs"])
        
        sample = {
            "messages": [
                {"role": "user", "content": f"{instruction}\n\n{input_text}"},
                {"role": "assistant", "content": f"[Generated response for sample {i+1} — replace with real output]"},
            ]
        }
        samples.append(sample)
    
    with open(output_path, "w", encoding="utf-8") as f:
        for sample in samples:
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")
    
    print(f"Generated {num_samples} samples → {output_path}")
    print(f"\n⚠️  IMPORTANT: These are placeholder responses.")
    print(f"   Replace with real outputs, or use --llm for high-quality generation.")
    print(f"\nFormat preview:")
    print(json.dumps(samples[0], indent=2))


def main():
    parser = argparse.ArgumentParser(description="Generate SFT training data")
    parser.add_argument("--task", type=str, default="chat",
                       choices=list(TASK_TEMPLATES.keys()),
                       help="Task type to generate (default: chat)")
    parser.add_argument("--num-samples", type=int, default=100,
                       help="Number of samples (default: 100)")
    parser.add_argument("--output", type=str, default="training_data.jsonl",
                       help="Output file (default: training_data.jsonl)")
    parser.add_argument("--llm", action="store_true",
                       help="Use LLM API for high-quality generation (requires OPENAI_API_KEY)")
    
    args = parser.parse_args()
    
    if args.llm:
        print("LLM generation requires OPENAI_API_KEY environment variable.")
        print("Alternatively, use the Colab notebook's Option C to create data inline.")
        sys.exit(1)
    
    generate_simple_task(args.task, args.num_samples, args.output)


if __name__ == "__main__":
    main()
