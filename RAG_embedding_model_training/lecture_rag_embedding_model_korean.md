---
marp: true
theme: default
paginate: true
style: |
  section { font-size: 22px; }
  pre { font-size: 15px; }
  code { font-size: 15px; }
  h1 { font-size: 36px; }
  h2 { font-size: 28px; }
---

# RAG 임베딩 모델 (Bi-Encoder)
## PyTorch로 구현하는 검색용 임베딩 모델

---

## RAG (Retrieval-Augmented Generation) 개요

- **문제**: LLM은 학습 시점 이후의 지식, 도메인 특화 정보 부족
- **해결**: 외부 문서를 실시간 검색하여 LLM에 컨텍스트로 제공
- **핵심 2단계**:
  - `Retrieval` — 쿼리와 유사한 문서를 벡터 DB에서 검색
  - `Generation` — 검색된 문서를 LLM 프롬프트에 삽입하여 답변 생성

```
[Query] → [Embedding Model] → [Vector Search] → [Top-K Passages]
                                                        ↓
                                              [LLM + Passages] → [Answer]
```

---

## Bi-Encoder 구조

- **쿼리와 패시지가 동일한 인코더(가중치 공유)**를 통과
- 각각 독립적으로 고정 크기 벡터로 인코딩
- **코사인 유사도**로 검색 → 대규모 배치 처리 가능

```
Query  → [Encoder] → q_emb (64-dim, L2 norm)
                                              → cosine_sim(q, p)
Passage → [Encoder] → p_emb (64-dim, L2 norm)
```

- **장점**: 패시지를 미리 인덱싱 가능 → 검색 속도 O(1)
- **vs Cross-Encoder**: Cross-Encoder는 (Q, P) 동시 입력 → 정확하지만 느림

---

## 전체 학습 파이프라인

```
합성 데이터 (Query, Passage 쌍)
        ↓
  SimpleTokenizer
        ↓
  EmbeddingModel (Transformer Bi-Encoder)
  ├─ TokenEmbedding (token + positional)
  ├─ TransformerEncoderLayer × N (Pre-LN)
  ├─ Mean Pooling
  └─ Projection + L2 Normalize
        ↓
  InfoNCE Loss (In-batch Negatives)
        ↓
  AdamW + Linear Warmup + Cosine Decay
        ↓
  평가: MRR@10, Recall@K
```

---

## 모델 Config

```python
@dataclass
class ModelConfig:
    vocab_size : int   = 30_522  # BERT WordPiece 호환 어휘
    max_seq_len: int   = 32      # 최대 토큰 수
    d_model    : int   = 128     # Transformer 히든 차원
    n_heads    : int   = 4       # Multi-Head Attention 수
    n_layers   : int   = 2       # Transformer 레이어 수
    d_ff       : int   = 256     # FFN 히든 차원
    dropout    : float = 0.1
    embed_dim  : int   = 64      # 최종 임베딩 차원

@dataclass
class TrainConfig:
    batch_size   : int   = 16
    learning_rate: float = 2e-4
    warmup_steps : int   = 100
    epochs       : int   = 5
    temperature  : float = 0.05  # InfoNCE 온도 파라미터
    synthetic_n  : int   = 2_000
```

- `temperature` 값이 낮을수록 → 유사도 분포가 더 sharp (hard contrast)

---

## 토크나이저 (SimpleTokenizer)

- 공백 기준 토크나이징 + 특수 토큰 삽입
- 특수 토큰: `[PAD]=0`, `[UNK]=1`, `[CLS]=2`, `[SEP]=3`

```python
def encode(self, text: str):
    word_ids = [self._get_id(w.lower()) for w in text.split()]
    # [CLS] + tokens (max_seq_len-2개) + [SEP]
    tokens = [self.CLS] + word_ids[:self.max_seq_len - 2] + [self.SEP]
    pad_len = self.max_seq_len - len(tokens)
    input_ids      = tokens + [self.PAD] * pad_len
    attention_mask = [1]    * len(tokens) + [0] * pad_len
    return (
        torch.tensor(input_ids),
        torch.tensor(attention_mask)
    )
```

---

## Token + Positional Embedding

- **Token Embedding**: 단어의 의미 벡터
- **Positional Embedding**: 위치 정보 (sin/cos 패턴으로 초기화)

```python
class TokenEmbedding(nn.Module):
    def __init__(self, cfg):
        self.token_emb = nn.Embedding(cfg.vocab_size, cfg.d_model, padding_idx=0)
        self.pos_emb   = nn.Embedding(cfg.max_seq_len, cfg.d_model)
        # sin/cos 초기화 → 학습 안정성↑
        pos = torch.arange(cfg.max_seq_len).unsqueeze(1).float()
        dim = torch.arange(0, cfg.d_model, 2).float()
        pe[:, 0::2] = torch.sin(pos / 10000 ** (dim / cfg.d_model))  # 짝수
        pe[:, 1::2] = torch.cos(pos / 10000 ** (dim / cfg.d_model))  # 홀수

    def forward(self, input_ids):
        positions = torch.arange(input_ids.size(1), device=input_ids.device)
        x = self.token_emb(input_ids) + self.pos_emb(positions)
        return self.drop(self.norm(x))  # LayerNorm + Dropout
```

---

## Transformer Encoder Layer (Pre-LN)

- **Pre-LayerNorm**: Attention/FFN 이전에 정규화 → 학습 안정성↑
- **Residual Connection**: 그래디언트 소실 방지

```python
class TransformerEncoderLayer(nn.Module):
    def forward(self, x, key_padding_mask):
        # ① Self-Attention (Pre-LN)
        residual = x
        x = self.norm1(x)                                # 먼저 정규화
        x, _ = self.attn(x, x, x,
                         key_padding_mask=key_padding_mask)
        x = self.drop(x) + residual                     # Residual

        # ② Feed-Forward (Pre-LN)
        residual = x
        x = self.norm2(x)
        x = self.ff(x)                                   # Linear → GELU → Linear
        x = self.drop(x) + residual                     # Residual
        return x
```

---

## EmbeddingModel 전체 구조

```python
class EmbeddingModel(nn.Module):
    def forward(self, input_ids, attention_mask):
        # 1. Token + Positional Embedding
        x = self.embedding(input_ids)           # (B, L, d_model)

        # 2. Transformer Layers (패딩 마스크 전달)
        key_padding_mask = (attention_mask == 0)
        for layer in self.layers:
            x = layer(x, key_padding_mask)      # (B, L, d_model)

        # 3. Mean Pooling (패딩 토큰 제외)
        mask = attention_mask.unsqueeze(-1).float()
        x = (x * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1e-9)  # (B, d_model)

        # 4. Projection Head
        x = self.proj(x)                        # (B, embed_dim)

        # 5. L2 정규화 → 코사인 유사도 = 내적
        return F.normalize(x, p=2, dim=-1)
```

---

## InfoNCE Loss — 이론

- **Contrastive Learning**: 유사한 쌍은 가깝게, 무관한 쌍은 멀리
- **In-batch Negatives**: 같은 배치 내 다른 패시지를 자동으로 Negative 활용

```
배치 크기 B = 4 예시:

         p0      p1      p2      p3
q0  [ ✓ high  low    low    low  ]  → q0은 p0과만 매칭
q1  [ low   ✓ high  low    low  ]
q2  [ low    low   ✓ high  low  ]
q3  [ low    low    low   ✓ high]
```

- **Temperature τ**: 낮을수록 분포 sharp → hard negative 효과
- **대각선**이 정답 레이블 (i번째 쿼리 → i번째 패시지)

---

## InfoNCE Loss — 코드

```python
class InfoNCELoss(nn.Module):
    def forward(self, q_emb, p_emb):
        B = q_emb.size(0)

        # B×B 코사인 유사도 행렬 (L2 정규화 완료 → 내적 = 코사인)
        sim = torch.matmul(q_emb, p_emb.T) / self.temperature  # (B, B)

        # 정답 레이블: 대각선 (i번 쿼리 = i번 패시지)
        labels = torch.arange(B, device=q_emb.device)

        # 양방향 Cross-Entropy Loss
        loss_qp = F.cross_entropy(sim,   labels)  # Query → Passage
        loss_pq = F.cross_entropy(sim.T, labels)  # Passage → Query
        return (loss_qp + loss_pq) / 2
```

---

## 합성 데이터셋

- **(Query, Positive Passage)** 쌍으로 구성
- 템플릿 기반 자동 생성 (ML, NLP, 신호처리, 유전체학 도메인)

```python
class TripletDataset(Dataset):
    def __getitem__(self, idx):
        query, passage = self.pairs[idx]
        q_ids, q_mask = self.tokenizer.encode(query)
        p_ids, p_mask = self.tokenizer.encode(passage)
        return q_ids, q_mask, p_ids, p_mask

def make_synthetic_pairs(n=2_000):
    templates = [
        ('What is {concept}?',       '{concept} is a core concept in {field}...'),
        ('How does {concept} work?', 'The mechanism of {concept} involves...'),
        ('Explain {concept}',        '{concept} can be understood as...'),
    ]
    concepts = [
        ('gradient descent', 'machine learning', '...'),
        ('attention mechanism', 'NLP', '...'),
        # ...
    ]
```

---

## 평가 지표 — MRR & Recall@K

- **MRR@10** (Mean Reciprocal Rank): 정답 패시지의 순위 역수 평균
  - 정답이 1위 → 1.0, 2위 → 0.5, 3위 → 0.33
- **Recall@K**: 상위 K개 결과 안에 정답이 있는 비율

```python
def evaluate(model, val_loader, device):
    # 전체 쿼리/패시지 임베딩 계산
    sim = torch.matmul(Q, P.T)          # N×N 유사도 행렬

    # 대각선(정답) 점수보다 높은 항목 수 → 랭킹 계산
    ranks = (sim > sim.diagonal().unsqueeze(1)).sum(dim=1) + 1

    return {
        'MRR@10': (1.0 / ranks.float().clamp(max=10)).mean().item(),
        'R@1' : (ranks <= 1).float().mean().item(),
        'R@5' : (ranks <= 5).float().mean().item(),
        'R@10': (ranks <= 10).float().mean().item(),
    }
```

---

## 학습 루프

```python
for epoch in range(1, train_cfg.epochs + 1):
    for batch in train_loader:
        q_ids, q_mask, p_ids, p_mask = [x.to(device) for x in batch]

        # Forward
        q_emb = model(q_ids, q_mask)   # (B, 64)
        p_emb = model(p_ids, p_mask)   # (B, 64)
        loss  = criterion(q_emb, p_emb)

        # Backward
        optimizer.zero_grad()
        loss.backward()
        # Gradient Clipping: 폭발적 그래디언트 방지
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        scheduler.step()

        # 주기적 평가 (매 eval_every 스텝)
        if step % train_cfg.eval_every == 0:
            metrics = evaluate(model, val_loader, device)
```

---

## LR 스케줄러 — Warmup + Cosine Decay

- **Linear Warmup**: 초반 불안정한 그래디언트 → LR을 서서히 증가
- **Cosine Decay**: 이후 코사인 곡선으로 LR 감소 → 수렴 안정성↑

```python
def get_scheduler(optimizer, warmup_steps, total_steps):
    def lr_lambda(step):
        if step < warmup_steps:
            return step / max(1, warmup_steps)      # Linear Warmup
        progress = (step - warmup_steps) / max(1, total_steps - warmup_steps)
        return 0.5 * (1.0 + math.cos(math.pi * progress))  # Cosine Decay
    return LambdaLR(optimizer, lr_lambda)
```

```
LR
▲
│   /\
│  /  \___
│ /        ‾‾‾──
│/
└──────────────→ steps
 warmup  cosine decay
```

---

## RAG Retriever

- **index()**: 패시지 임베딩 사전 계산 → 벡터 DB 역할
- **search()**: 쿼리 임베딩 계산 → 내적으로 Top-K 검색

```python
class RAGRetriever:
    def index(self, passages: list[str]):
        self._passages = passages
        self._index = self._embed(passages)   # (N, 64)

    def search(self, query: str, top_k: int = 3):
        q_emb  = self._embed([query])                     # (1, 64)
        scores = (q_emb @ self._index.T).squeeze(0)       # (N,)
        top_ids = scores.topk(top_k).indices
        return [
            (rank + 1, scores[i].item(), self._passages[i])
            for rank, i in enumerate(top_ids)
        ]
```

- `_embed()` 내부에서 `model.eval()` + `torch.no_grad()` 적용

---

## 임베딩 공간 시각화 (PCA)

- **PCA 2D**: 고차원 임베딩을 2차원으로 축소하여 군집 확인
- **학습 후**: 쿼리-패시지 쌍이 가까운 위치에 군집

```python
from sklearn.decomposition import PCA

pca = PCA(n_components=2)
xy  = pca.fit_transform(embs)   # (2N, 2)

# 쿼리: ●  패시지: ■  → 같은 색 = 동일 쌍
# 점선: 쿼리-패시지 연결
for i, (q_xy, p_xy) in enumerate(zip(q_points, p_points)):
    plt.plot([q_xy[0], p_xy[0]], [q_xy[1], p_xy[1]],
             'k--', alpha=0.3)
```

| 학습 전 | 학습 후 |
|---|---|
| 쿼리-패시지 쌍 분산 배치 | 동일 쌍이 인접한 위치로 수렴 |
| MRR@10 ≈ 0.01 (랜덤 수준) | MRR@10 ≈ 0.7+ |
