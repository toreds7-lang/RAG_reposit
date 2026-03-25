"""
RAG Embedding Model - PyTorch Training from Scratch
====================================================
Bi-Encoder with:
  - Custom Transformer encoder (Embedding + N×TransformerLayer)
  - Mean pooling + projection head + L2 normalization
  - InfoNCE loss with in-batch negatives
  - MS MARCO-style dataset (or synthetic fallback)
  - MRR@10 / Recall@K evaluation

Usage:
    pip install torch datasets tqdm

    # Quick run with synthetic data (no download needed):
    python rag_embedding_model.py --synthetic --epochs 10

    # With MS MARCO:
    python rag_embedding_model.py --dataset msmarco --epochs 3
"""

import math
import argparse
import random
from pathlib import Path
from dataclasses import dataclass

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from tqdm import tqdm


# ──────────────────────────────────────────────
# 1. Configuration
# ──────────────────────────────────────────────

@dataclass
class ModelConfig:
    vocab_size: int   = 30_522   # matches BERT WordPiece tokenizer
    max_seq_len: int  = 128
    d_model: int      = 512
    n_heads: int      = 8
    n_layers: int     = 6
    d_ff: int         = 2048     # feedforward hidden dim
    dropout: float    = 0.1
    embed_dim: int    = 256      # final output embedding dim

@dataclass
class TrainConfig:
    batch_size: int      = 64
    learning_rate: float = 2e-4
    warmup_steps: int    = 1000
    epochs: int          = 3
    temperature: float   = 0.05   # InfoNCE temperature τ
    max_grad_norm: float = 1.0
    eval_every: int      = 500    # steps
    save_path: str       = "embedding_model.pt"
    device: str          = "cuda" if torch.cuda.is_available() else "cpu"


# ──────────────────────────────────────────────
# 2. Simple WordPiece-compatible Tokenizer
#    (Uses transformers if available, else falls
#     back to whitespace tokenizer for demo)
# ──────────────────────────────────────────────

class SimpleTokenizer:
    """
    Whitespace tokenizer with a small fixed vocabulary.
    Drop-in replacement for HuggingFace tokenizer when
    running in demo / synthetic mode.
    """
    PAD, UNK, CLS, SEP = 0, 1, 2, 3
    SPECIAL = {"[PAD]": 0, "[UNK]": 1, "[CLS]": 2, "[SEP]": 3}

    def __init__(self, max_seq_len: int = 128):
        self.max_seq_len = max_seq_len
        self.word2id = dict(self.SPECIAL)
        self.next_id = len(self.word2id)

    def _get_id(self, w: str) -> int:
        if w not in self.word2id:
            self.word2id[w] = self.next_id
            self.next_id += 1
        return self.word2id[w]

    def encode(self, text: str) -> dict:
        tokens = [self.CLS] + [
            self._get_id(w.lower()) for w in text.split()
        ][:self.max_seq_len - 2] + [self.SEP]

        pad_len = self.max_seq_len - len(tokens)
        input_ids      = tokens + [self.PAD] * pad_len
        attention_mask = [1] * len(tokens) + [0] * pad_len
        return {
            "input_ids":      torch.tensor(input_ids,      dtype=torch.long),
            "attention_mask": torch.tensor(attention_mask, dtype=torch.long),
        }

    @property
    def vocab_size(self):
        return max(30_522, self.next_id)   # keep compatible with ModelConfig


def get_tokenizer(use_bert: bool = False, max_seq_len: int = 128):
    if use_bert:
        try:
            from transformers import AutoTokenizer

            class HFTokenizerWrapper:
                def __init__(self, hf_tok, max_len):
                    self.tok = hf_tok
                    self.max_seq_len = max_len

                def encode(self, text: str) -> dict:
                    enc = self.tok(
                        text,
                        max_length=self.max_seq_len,
                        padding="max_length",
                        truncation=True,
                        return_tensors="pt",
                    )
                    return {k: v.squeeze(0) for k, v in enc.items()
                            if k in ("input_ids", "attention_mask")}

            hf = AutoTokenizer.from_pretrained("bert-base-uncased")
            print("✅  Using BERT WordPiece tokenizer")
            return HFTokenizerWrapper(hf, max_seq_len)
        except ImportError:
            print("⚠️  transformers not installed — using SimpleTokenizer")

    return SimpleTokenizer(max_seq_len)


# ──────────────────────────────────────────────
# 3. Model Architecture
# ──────────────────────────────────────────────

class TokenEmbedding(nn.Module):
    """Token + positional embedding with dropout."""

    def __init__(self, cfg: ModelConfig):
        super().__init__()
        self.token_emb = nn.Embedding(cfg.vocab_size, cfg.d_model, padding_idx=0)
        self.pos_emb   = nn.Embedding(cfg.max_seq_len, cfg.d_model)
        self.norm      = nn.LayerNorm(cfg.d_model)
        self.drop      = nn.Dropout(cfg.dropout)

        # sinusoidal init for positional embeddings
        pos = torch.arange(cfg.max_seq_len).unsqueeze(1)
        dim = torch.arange(0, cfg.d_model, 2)
        pe  = torch.zeros(cfg.max_seq_len, cfg.d_model)
        pe[:, 0::2] = torch.sin(pos / 10000 ** (dim / cfg.d_model))
        pe[:, 1::2] = torch.cos(pos / 10000 ** (dim / cfg.d_model))
        self.pos_emb.weight.data.copy_(pe)

    def forward(self, input_ids: torch.Tensor) -> torch.Tensor:
        B, L = input_ids.shape
        positions = torch.arange(L, device=input_ids.device).unsqueeze(0)
        x = self.token_emb(input_ids) + self.pos_emb(positions)
        return self.drop(self.norm(x))


class TransformerEncoderLayer(nn.Module):
    """
    Pre-LN Transformer layer (more stable training than post-LN).
    Multi-head self-attention → Feed-forward.
    """

    def __init__(self, cfg: ModelConfig):
        super().__init__()
        self.attn  = nn.MultiheadAttention(
            cfg.d_model, cfg.n_heads,
            dropout=cfg.dropout, batch_first=True
        )
        self.ff    = nn.Sequential(
            nn.Linear(cfg.d_model, cfg.d_ff),
            nn.GELU(),
            nn.Dropout(cfg.dropout),
            nn.Linear(cfg.d_ff, cfg.d_model),
        )
        self.norm1 = nn.LayerNorm(cfg.d_model)
        self.norm2 = nn.LayerNorm(cfg.d_model)
        self.drop  = nn.Dropout(cfg.dropout)

    def forward(self, x: torch.Tensor, key_padding_mask: torch.Tensor) -> torch.Tensor:
        # Pre-LN self-attention
        residual = x
        x = self.norm1(x)
        x, _ = self.attn(x, x, x, key_padding_mask=key_padding_mask)
        x = self.drop(x) + residual

        # Pre-LN feed-forward
        residual = x
        x = self.norm2(x)
        x = self.ff(x)
        x = self.drop(x) + residual
        return x


class EmbeddingModel(nn.Module):
    """
    Bi-Encoder Embedding Model.

    Encode(text) → fixed-size L2-normalized vector of shape (embed_dim,).

    Forward pass:
        input_ids      : (B, L) long
        attention_mask : (B, L) bool/long  1=real token, 0=padding

    Returns:
        embeddings : (B, embed_dim) float, L2-normalized
    """

    def __init__(self, cfg: ModelConfig):
        super().__init__()
        self.embedding = TokenEmbedding(cfg)
        self.layers    = nn.ModuleList([
            TransformerEncoderLayer(cfg) for _ in range(cfg.n_layers)
        ])
        self.proj = nn.Sequential(
            nn.Linear(cfg.d_model, cfg.d_model),
            nn.GELU(),
            nn.Linear(cfg.d_model, cfg.embed_dim),
        )

    def encode(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor,
    ) -> torch.Tensor:
        # key_padding_mask: True where we should IGNORE (i.e. padding)
        key_padding_mask = (attention_mask == 0)          # (B, L)

        x = self.embedding(input_ids)                    # (B, L, D)
        for layer in self.layers:
            x = layer(x, key_padding_mask)

        # Mean pooling over non-padding tokens
        mask_expanded = attention_mask.unsqueeze(-1).float()  # (B, L, 1)
        x = (x * mask_expanded).sum(dim=1) / mask_expanded.sum(dim=1).clamp(min=1e-9)

        x = self.proj(x)                                 # (B, embed_dim)
        return F.normalize(x, p=2, dim=-1)               # L2 normalize

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor,
    ) -> torch.Tensor:
        return self.encode(input_ids, attention_mask)

    def count_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


# ──────────────────────────────────────────────
# 4. InfoNCE Loss (in-batch negatives)
# ──────────────────────────────────────────────

class InfoNCELoss(nn.Module):
    """
    Symmetric InfoNCE / NT-Xent contrastive loss.

    For a batch of (query, positive_passage) pairs of size B:
      - The B×B cosine similarity matrix acts as logits.
      - Diagonal entries are positive pairs.
      - Off-diagonal are in-batch negatives (free!).

    Temperature τ controls how sharply peaked the distribution is.
    Lower τ → harder negatives → faster convergence but more instability.
    """

    def __init__(self, temperature: float = 0.05):
        super().__init__()
        self.temperature = temperature

    def forward(
        self,
        q_emb: torch.Tensor,   # (B, D) normalized
        p_emb: torch.Tensor,   # (B, D) normalized
    ) -> torch.Tensor:
        B = q_emb.size(0)

        # Cosine similarity matrix (already normalized → dot product = cosine)
        sim = torch.matmul(q_emb, p_emb.T) / self.temperature  # (B, B)

        # Labels: diagonal (query i matches passage i)
        labels = torch.arange(B, device=q_emb.device)

        # Cross-entropy in both directions (symmetric)
        loss_qp = F.cross_entropy(sim,   labels)   # query→passage
        loss_pq = F.cross_entropy(sim.T, labels)   # passage→query

        return (loss_qp + loss_pq) / 2


# ──────────────────────────────────────────────
# 5. Dataset
# ──────────────────────────────────────────────

class TripletDataset(Dataset):
    """
    Expects a list of dicts:  {"query": str, "positive": str}
    Negative is sampled in-batch during loss computation — no explicit
    negative column needed.
    """

    def __init__(self, pairs: list[dict], tokenizer, max_seq_len: int = 128):
        self.pairs     = pairs
        self.tokenizer = tokenizer
        self.max_seq_len = max_seq_len

    def __len__(self):
        return len(self.pairs)

    def __getitem__(self, idx):
        item = self.pairs[idx]
        q = self.tokenizer.encode(item["query"])
        p = self.tokenizer.encode(item["positive"])
        return {
            "q_input_ids":      q["input_ids"],
            "q_attention_mask": q["attention_mask"],
            "p_input_ids":      p["input_ids"],
            "p_attention_mask": p["attention_mask"],
        }


def load_msmarco(split: str = "train", max_samples: int = 100_000) -> list[dict]:
    """Load MS MARCO passage ranking pairs via HuggingFace datasets."""
    from datasets import load_dataset
    print(f"⏳  Loading MS MARCO ({split}, up to {max_samples:,} samples)…")
    ds = load_dataset("ms_marco", "v1.1", split=split, streaming=True)
    pairs = []
    for row in ds:
        # MS MARCO: passages field has a list of texts + is_selected flags
        for text, selected in zip(
            row["passages"]["passage_text"],
            row["passages"]["is_selected"],
        ):
            if selected == 1:
                pairs.append({"query": row["query"], "positive": text})
                break
        if len(pairs) >= max_samples:
            break
    print(f"✅  Loaded {len(pairs):,} query-passage pairs")
    return pairs


def make_synthetic_pairs(n: int = 10_000) -> list[dict]:
    """
    Generate simple synthetic (query, positive) pairs for demo purposes.
    Topics: science, history, geography, tech.
    """
    templates = [
        ("What is {concept}?",
         "{concept} is a fundamental concept in {field} that involves {detail}."),
        ("How does {concept} work?",
         "The mechanism of {concept} relies on {detail}, which is key in {field}."),
        ("Why is {concept} important?",
         "{concept} plays a critical role in {field} because {detail}."),
        ("When was {concept} discovered?",
         "{concept} was first described in the context of {field}, relating to {detail}."),
        ("Where is {concept} used?",
         "{concept} is widely applied in {field}, particularly involving {detail}."),
    ]
    concepts = [
        ("photosynthesis",     "biology",    "converting sunlight into glucose"),
        ("gradient descent",   "ML",         "minimizing loss by following negative gradient"),
        ("attention mechanism","NLP",        "computing weighted sums over token representations"),
        ("plate tectonics",    "geology",    "movement of Earth's lithospheric plates"),
        ("quantum entanglement","physics",   "correlated quantum states across distance"),
        ("transformer model",  "deep learning","self-attention and feedforward layers"),
        ("CRISPR",             "genomics",   "targeted DNA editing using guide RNA"),
        ("black holes",        "astrophysics","regions of spacetime with extreme gravity"),
        ("Fourier transform",  "signal processing","decomposing signals into frequency components"),
        ("backpropagation",    "neural networks","computing gradients via chain rule"),
    ]
    pairs = []
    for _ in range(n):
        q_tmpl, p_tmpl = random.choice(templates)
        concept, field, detail = random.choice(concepts)
        pairs.append({
            "query":    q_tmpl.format(concept=concept, field=field, detail=detail),
            "positive": p_tmpl.format(concept=concept, field=field, detail=detail),
        })
    return pairs


# ──────────────────────────────────────────────
# 6. Learning Rate Scheduler (Linear Warmup + Cosine)
# ──────────────────────────────────────────────

def get_scheduler(optimizer, warmup_steps: int, total_steps: int):
    def lr_lambda(step):
        if step < warmup_steps:
            return step / max(1, warmup_steps)
        progress = (step - warmup_steps) / max(1, total_steps - warmup_steps)
        return max(0.0, 0.5 * (1.0 + math.cos(math.pi * progress)))

    return torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)


# ──────────────────────────────────────────────
# 7. Evaluation: MRR@10 and Recall@K
# ──────────────────────────────────────────────

@torch.no_grad()
def evaluate(model, val_loader, device: str, top_k: int = 10) -> dict:
    """
    Computes MRR@10 and Recall@{1,5,10} on a validation set.
    Assumes diagonal ground truth (query i → passage i).
    """
    model.eval()
    all_q, all_p = [], []

    for batch in val_loader:
        q_emb = model(
            batch["q_input_ids"].to(device),
            batch["q_attention_mask"].to(device),
        )
        p_emb = model(
            batch["p_input_ids"].to(device),
            batch["p_attention_mask"].to(device),
        )
        all_q.append(q_emb.cpu())
        all_p.append(p_emb.cpu())

    Q = torch.cat(all_q)  # (N, D)
    P = torch.cat(all_p)  # (N, D)

    # Full similarity matrix
    sim = torch.matmul(Q, P.T)  # (N, N)
    ranks = (sim > sim.diagonal().unsqueeze(1)).sum(dim=1) + 1  # 1-indexed rank

    n = len(ranks)
    mrr = (1.0 / ranks.float()).mean().item()
    r1  = (ranks <= 1).float().mean().item()
    r5  = (ranks <= 5).float().mean().item()
    r10 = (ranks <= 10).float().mean().item()

    model.train()
    return {"MRR@10": mrr, "R@1": r1, "R@5": r5, "R@10": r10}


# ──────────────────────────────────────────────
# 8. Training Loop
# ──────────────────────────────────────────────

def train(model_cfg: ModelConfig, train_cfg: TrainConfig, args):
    device = train_cfg.device
    print(f"🖥️   Device: {device}")

    # ── Tokenizer ──────────────────────────────
    tokenizer = get_tokenizer(
        use_bert=args.use_bert_tokenizer,
        max_seq_len=model_cfg.max_seq_len,
    )

    # ── Data ───────────────────────────────────
    if args.synthetic:
        print("🔧  Generating synthetic data…")
        all_pairs = make_synthetic_pairs(n=args.synthetic_n)
    else:
        all_pairs = load_msmarco(split="train", max_samples=args.max_samples)

    split = int(0.95 * len(all_pairs))
    train_pairs = all_pairs[:split]
    val_pairs   = all_pairs[split:]
    print(f"📦  Train: {len(train_pairs):,}  |  Val: {len(val_pairs):,}")

    train_ds = TripletDataset(train_pairs, tokenizer, model_cfg.max_seq_len)
    val_ds   = TripletDataset(val_pairs,   tokenizer, model_cfg.max_seq_len)

    train_loader = DataLoader(
        train_ds, batch_size=train_cfg.batch_size,
        shuffle=True, num_workers=0, pin_memory=(device == "cuda"),
    )
    val_loader = DataLoader(
        val_ds, batch_size=train_cfg.batch_size * 2,
        shuffle=False, num_workers=0,
    )

    # ── Model ──────────────────────────────────
    # Update vocab size if using SimpleTokenizer (vocab grows dynamically)
    if hasattr(tokenizer, "vocab_size"):
        model_cfg.vocab_size = max(model_cfg.vocab_size, tokenizer.vocab_size)

    model = EmbeddingModel(model_cfg).to(device)
    print(f"🧠  Parameters: {model.count_parameters():,}")

    # ── Optimizer, Loss, Scheduler ─────────────
    optimizer  = torch.optim.AdamW(
        model.parameters(), lr=train_cfg.learning_rate, weight_decay=0.01
    )
    criterion  = InfoNCELoss(temperature=train_cfg.temperature)
    total_steps = len(train_loader) * train_cfg.epochs
    scheduler  = get_scheduler(optimizer, train_cfg.warmup_steps, total_steps)

    # ── AMP (fp16) if CUDA ─────────────────────
    scaler = torch.cuda.amp.GradScaler() if device == "cuda" else None

    # ── Training ───────────────────────────────
    step = 0
    best_mrr = 0.0

    for epoch in range(1, train_cfg.epochs + 1):
        model.train()
        epoch_loss = 0.0
        pbar = tqdm(train_loader, desc=f"Epoch {epoch}/{train_cfg.epochs}")

        for batch in pbar:
            q_ids  = batch["q_input_ids"].to(device)
            q_mask = batch["q_attention_mask"].to(device)
            p_ids  = batch["p_input_ids"].to(device)
            p_mask = batch["p_attention_mask"].to(device)

            optimizer.zero_grad()

            if scaler:
                with torch.cuda.amp.autocast():
                    q_emb = model(q_ids, q_mask)
                    p_emb = model(p_ids, p_mask)
                    loss  = criterion(q_emb, p_emb)
                scaler.scale(loss).backward()
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(
                    model.parameters(), train_cfg.max_grad_norm
                )
                scaler.step(optimizer)
                scaler.update()
            else:
                q_emb = model(q_ids, q_mask)
                p_emb = model(p_ids, p_mask)
                loss  = criterion(q_emb, p_emb)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(
                    model.parameters(), train_cfg.max_grad_norm
                )
                optimizer.step()

            scheduler.step()
            step += 1
            epoch_loss += loss.item()
            pbar.set_postfix(
                loss=f"{loss.item():.4f}",
                lr=f"{scheduler.get_last_lr()[0]:.2e}",
            )

            # Periodic evaluation
            if step % train_cfg.eval_every == 0:
                metrics = evaluate(model, val_loader, device)
                mrr = metrics["MRR@10"]
                print(
                    f"\n📊  Step {step:,} | "
                    + " | ".join(f"{k}: {v:.4f}" for k, v in metrics.items())
                )
                if mrr > best_mrr:
                    best_mrr = mrr
                    torch.save(
                        {"model_state": model.state_dict(), "config": model_cfg},
                        train_cfg.save_path,
                    )
                    print(f"   💾  Saved best model (MRR@10={mrr:.4f})")
                model.train()

        avg_loss = epoch_loss / len(train_loader)
        print(f"Epoch {epoch} avg loss: {avg_loss:.4f}")

    # Final evaluation
    print("\n── Final Evaluation ──")
    metrics = evaluate(model, val_loader, device)
    print(" | ".join(f"{k}: {v:.4f}" for k, v in metrics.items()))
    print(f"\n✅  Training complete. Best MRR@10: {best_mrr:.4f}")
    print(f"   Model saved to: {train_cfg.save_path}")
    return model


# ──────────────────────────────────────────────
# 9. Inference Utilities
# ──────────────────────────────────────────────

class RAGRetriever:
    """
    Thin wrapper around a trained EmbeddingModel for RAG retrieval.

    Usage:
        retriever = RAGRetriever.load("embedding_model.pt")
        retriever.index(passages)
        results = retriever.search("your query", top_k=5)
    """

    def __init__(self, model: EmbeddingModel, tokenizer, device: str = "cpu"):
        self.model     = model.eval().to(device)
        self.tokenizer = tokenizer
        self.device    = device
        self._index: torch.Tensor | None = None
        self._passages: list[str] = []

    @classmethod
    def load(cls, path: str, device: str = "cpu"):
        checkpoint  = torch.load(path, map_location=device)
        cfg         = checkpoint["config"]
        model       = EmbeddingModel(cfg)
        model.load_state_dict(checkpoint["model_state"])
        tokenizer   = get_tokenizer(max_seq_len=cfg.max_seq_len)
        return cls(model, tokenizer, device)

    @torch.no_grad()
    def _embed(self, texts: list[str]) -> torch.Tensor:
        all_embs = []
        for text in texts:
            enc = self.tokenizer.encode(text)
            emb = self.model(
                enc["input_ids"].unsqueeze(0).to(self.device),
                enc["attention_mask"].unsqueeze(0).to(self.device),
            )
            all_embs.append(emb)
        return torch.cat(all_embs, dim=0)

    def index(self, passages: list[str], batch_size: int = 128):
        """Build a flat cosine index over passages."""
        print(f"📚  Indexing {len(passages):,} passages…")
        self._passages = passages
        batches = []
        for i in range(0, len(passages), batch_size):
            batches.append(self._embed(passages[i:i + batch_size]))
        self._index = torch.cat(batches, dim=0)  # (N, D)
        print("✅  Index ready")

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Return top-k passages with scores."""
        if self._index is None:
            raise RuntimeError("Call .index() first.")
        q_emb = self._embed([query])                        # (1, D)
        scores = (q_emb @ self._index.T).squeeze(0)        # (N,)
        top_ids = scores.topk(top_k).indices.tolist()
        return [
            {"rank": i + 1, "score": scores[idx].item(), "passage": self._passages[idx]}
            for i, idx in enumerate(top_ids)
        ]


# ──────────────────────────────────────────────
# 10. Entry Point
# ──────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="Train a RAG embedding model from scratch")
    p.add_argument("--synthetic",        action="store_true",  help="Use synthetic data (no download)")
    p.add_argument("--synthetic_n",      type=int, default=10_000, help="# synthetic pairs")
    p.add_argument("--dataset",          type=str, default="msmarco")
    p.add_argument("--max_samples",      type=int, default=100_000)
    p.add_argument("--epochs",           type=int, default=3)
    p.add_argument("--batch_size",       type=int, default=64)
    p.add_argument("--lr",               type=float, default=2e-4)
    p.add_argument("--temperature",      type=float, default=0.05)
    p.add_argument("--d_model",          type=int, default=512)
    p.add_argument("--n_layers",         type=int, default=6)
    p.add_argument("--n_heads",          type=int, default=8)
    p.add_argument("--embed_dim",        type=int, default=256)
    p.add_argument("--max_seq_len",      type=int, default=128)
    p.add_argument("--eval_every",       type=int, default=500)
    p.add_argument("--use_bert_tokenizer", action="store_true", help="Use HF BERT tokenizer")
    p.add_argument("--save_path",        type=str, default="embedding_model.pt")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()

    model_cfg = ModelConfig(
        max_seq_len = args.max_seq_len,
        d_model     = args.d_model,
        n_heads     = args.n_heads,
        n_layers    = args.n_layers,
        embed_dim   = args.embed_dim,
    )
    train_cfg = TrainConfig(
        batch_size   = args.batch_size,
        learning_rate= args.lr,
        epochs       = args.epochs,
        temperature  = args.temperature,
        eval_every   = args.eval_every,
        save_path    = args.save_path,
    )

    model = train(model_cfg, train_cfg, args)

    # ── Quick inference demo ───────────────────
    print("\n── Inference Demo ──")
    tokenizer   = get_tokenizer(max_seq_len=model_cfg.max_seq_len)
    retriever   = RAGRetriever(model, tokenizer)
    demo_passages = [
        "Gradient descent minimizes a function by iteratively stepping in the negative gradient direction.",
        "Plate tectonics describes the motion of Earth's lithospheric plates over geological time.",
        "Attention mechanisms in transformers compute weighted sums of value vectors.",
        "CRISPR-Cas9 enables precise editing of genomic DNA sequences using guide RNAs.",
        "Black holes are regions of spacetime where gravity is so strong that nothing can escape.",
    ]
    retriever.index(demo_passages)
    results = retriever.search("how does the attention mechanism work?", top_k=3)
    print("\nQuery: 'how does the attention mechanism work?'")
    for r in results:
        print(f"  [{r['rank']}] score={r['score']:.4f} | {r['passage'][:80]}…")
