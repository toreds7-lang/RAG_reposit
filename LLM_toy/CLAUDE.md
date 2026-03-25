# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment

- Python 3.14 virtual environment managed by `uv` located at `.venv/`
- Activate: `source .venv/Scripts/activate` (Windows/bash)
- Install packages: `uv pip install -r requirements.txt`
- Run scripts: `python <script>.py`  or  `uv run python <script>.py`

## Project Purpose

Educational toy example demonstrating the full LLM lifecycle — no HuggingFace, no external frameworks. Pure PyTorch.

## 3-Stage Pipeline

```
python 01_pretrain.py   # ~2-3 min CPU, saves checkpoints/pretrain_final.pt
python 02_finetune.py   # ~30 sec CPU, saves checkpoints/finetune_final.pt
python 03_chat.py       # interactive chat
```

## File Roles

| File | Role |
|------|------|
| `tokenizer.py` | `CharTokenizer` — character-level tokenizer, vocab built from corpus |
| `model.py` | `ToyGPT` — 2-layer GPT transformer (~200K params), `CausalSelfAttention` manually implemented |
| `data.py` | `TextDataset` (sliding window) + `get_shakespeare()` (downloads & caches) |
| `01_pretrain.py` | Pre-trains ToyGPT on Tiny Shakespeare; saves tokenizer + model checkpoint |
| `02_finetune.py` | Fine-tunes on 25 Shakespeare Q&A pairs; shows Before/After comparison |
| `03_chat.py` | Streaming token-by-token chat; supports `/temp`, `/pretrain`, `/finetune`, `/reset` |

## Checkpoint Format

```python
{
  'model_state': ...,          # model.state_dict()
  'config': {vocab_size, context_len, d_model, n_layers, n_heads, d_ff, dropout},
  'train_losses': [...],
  'val_losses': [...],         # pretrain only
  'epoch': int,
}
```

## Model Hyperparameters (default)

`context_len=128, d_model=64, n_layers=2, n_heads=4, d_ff=256, dropout=0.1`

All hyperparameters are in a config block at the top of each training script.
