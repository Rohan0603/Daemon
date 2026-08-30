# Fine-tuning Guide: Qwen2.5-3B-Instruct with Unsloth

## Files Created

| File | Platform | Description |
|------|----------|-------------|
| `finetune_qwen2.5_3b_colab.ipynb` | Google Colab | Full SFT pipeline, free T4 GPU |
| `finetune_qwen2.5_3b_kaggle.ipynb` | Kaggle | Same pipeline, T4/P100 GPU |
| `unsloth-buddy/` | Local | Installed unsloth-buddy skill |

## Quick Start

### Option 1: Google Colab (Recommended)
1. Go to [colab.research.google.com](https://colab.research.google.com)
2. Click **File → Upload notebook** → select `finetune_qwen2.5_3b_colab.ipynb`
3. Go to **Runtime → Change runtime type → T4 GPU**
4. Click **Connect**, then **Runtime → Run all**

### Option 2: Kaggle
1. Go to [kaggle.com/code](https://www.kaggle.com/code)
2. Click **New Notebook → Import from file** → select `finetune_qwen2.5_3b_kaggle.ipynb`
3. Go to **Settings → Accelerator → GPU (T4 × 2)**
4. Click **Run All**

## Dataset Options

The notebooks include 3 dataset options:

### Option A: Quick Demo (Recommended for first run)
Uses `BAAI/Infinity-Instruct` from HuggingFace Hub — 500 samples, no setup needed.

### Option B: Upload Your Own Data
Upload a `.jsonl` or `.csv` file with columns like `question`/`answer` or `instruction`/`output`.

### Option C: Create Custom Dataset
Define training pairs inline in the notebook.

### Generate Synthetic Data (if you have no dataset)
Use this prompt with any LLM to generate training data:

```
I need to create a training dataset for fine-tuning Qwen2.5-3B for [YOUR TASK].
Generate 100 instruction-response pairs in JSONL format with "messages" field:
{"messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}

Task description: [DESCRIBE WHAT THE MODEL SHOULD DO]
Domain: [YOUR DOMAIN - e.g., customer support, code generation, healthcare]
Audience: [WHO WILL USE IT]
```

Save the output as `training_data.jsonl` and upload it to Colab/Kaggle.

## Key Hyperparameters

| Parameter | Default | Notes |
|-----------|---------|-------|
| `max_seq_length` | 2048 | Max token length per sample |
| `r` (LoRA rank) | 16 | Higher = more params, better quality |
| `learning_rate` | 2e-4 | Standard for QLoRA SFT |
| `max_steps` | 200 | Increase for real training (500-1000) |
| `batch_size` | 2 | Effective batch = 2 × 4 (grad_accum) = 8 |

## After Training

1. **Download adapters**: `lora_model/` folder from Colab file browser or Kaggle Output panel
2. **Test inference**: Cell 7 in the notebook
3. **Export to GGUF** (optional): Uncomment Cell 8 for Ollama/LM Studio deployment
4. **Push to Hub** (optional): Uncomment Cell 9 with your HF token

## Troubleshooting

| Issue | Fix |
|-------|-----|
| "No GPU detected" | Runtime → Change runtime type → GPU |
| OOM error | Reduce `per_device_train_batch_size` to 1 |
| Slow training | Increase `gradient_accumulation_steps` to 8 |
| Kaggle 30h limit | Use Colab for free tier, or Kaggle with paid compute |
| Unsloth install fails | `!pip install unsloth --no-deps` then restart runtime |

## Model Details

- **Base**: `unsloth/Qwen2.5-3B-Instruct-bnb-4bit` (4-bit QLoRA)
- **VRAM**: ~4-6 GB (fits on T4)
- **Speed**: ~2x faster than standard HuggingFace training
- **Export formats**: LoRA adapters (.safetensors), GGUF, merged 16-bit
