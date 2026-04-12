---
marp: true
theme: default
paginate: true
style: |
  section {
    font-size: 1.3rem;
  }
  code {
    font-size: 0.85rem;
  }
  h1 { color: #2c3e50; }
  h2 { color: #34495e; border-bottom: 2px solid #3498db; padding-bottom: 4px; }
---

# LLM_toy
## From Scratch GPT — 순수 PyTorch 구현

- HuggingFace, 외부 프레임워크 **없음**
- 순수 PyTorch로 LLM 전체 라이프사이클 구현
- 파라미터 수: **~200K** (CPU에서 수 분 내 학습 가능)
- 데이터: Tiny Shakespeare (~100K characters)

---

## Overview — 3-Stage Pipeline

```
Corpus (Text)
     │
     ▼
[Tokenizer]  ── 문자 → 정수 ID 매핑
     │
     ▼
[01_pretrain.py]  ── 대규모 텍스트로 언어 패턴 학습
     │
     ▼
[02_finetune.py]  ── 소규모 Q&A 데이터로 태스크 적응
     │
     ▼
[03_chat.py]  ── 스트리밍 토큰 생성, 대화 인터페이스
```

- 각 단계는 이전 단계의 체크포인트를 이어받음

---

## ToyGPT Architecture

```
Input IDs
  → Token Embedding + Position Embedding
  → Dropout
  → [TransformerBlock × 2]
       ├── LayerNorm → CausalSelfAttention → Residual
       └── LayerNorm → FeedForward → Residual
  → LayerNorm
  → LM Head (Linear, weight tied with Token Embedding)
  → Logits (vocab_size)
```

| 하이퍼파라미터 | 값 |
|---|---|
| `context_len` | 128 |
| `d_model` | 64 |
| `n_layers` | 2 |
| `n_heads` | 4 |
| `d_ff` | 256 |

---

## Tokenizer — 개념

- **Character-level tokenization**: 문자 단위로 vocab 구성
- 코퍼스에 등장하는 고유 문자만 수집 → vocab 크기 ~70
- `encode`: text → list of int
- `decode`: list of int → text
- 모델 학습 전 vocab 확정, 체크포인트와 함께 저장 필수

```
"Hello" → [32, 14, 21, 21, 24]
[32, 14, 21, 21, 24] → "Hello"
```

---

## Tokenizer — 핵심 코드

```python
class CharTokenizer:
    def __init__(self, text: str):
        chars = sorted(set(text))                          # 고유 문자 수집
        self.vocab     = {ch: i for i, ch in enumerate(chars)}
        self.inv_vocab = {i: ch for ch, i in self.vocab.items()}

    def encode(self, text: str) -> list:
        return [self.vocab[ch] for ch in text if ch in self.vocab]

    def decode(self, ids: list) -> str:
        return ''.join(self.inv_vocab.get(i, '') for i in ids)

    @property
    def vocab_size(self) -> int:
        return len(self.vocab)
```

---

## Model — Embedding

- **Token Embedding**: 각 토큰 ID → d_model 차원 벡터
- **Position Embedding**: 위치(0~T-1) → d_model 차원 벡터
- 두 임베딩을 **합산(sum)** 하여 입력 표현 구성
- **Weight Tying**: 입력 임베딩 가중치 = 출력 LM Head 가중치 (파라미터 절약)

```python
# 임베딩 합산
positions = torch.arange(T, device=idx.device)
x = self.drop(
    self.token_embedding(idx) + self.position_embedding(positions)
)

# Weight Tying
self.lm_head = nn.Linear(d_model, vocab_size, bias=False)
self.lm_head.weight = self.token_embedding.weight  # 가중치 공유
```

---

## Model — Causal Self-Attention

- **Causal Masking**: 미래 토큰을 볼 수 없도록 하삼각행렬 마스크 적용
- 마스킹된 위치 → `-inf` → softmax 후 0으로 수렴

```python
# 하삼각 마스크 등록 (학습 파라미터 아님)
mask = torch.tril(torch.ones(context_len, context_len))
self.register_buffer('mask', mask)

# Attention 계산
Q = self.q_proj(x)  # (B, T, d_model)
K = self.k_proj(x)
V = self.v_proj(x)

scores = Q @ K.transpose(-2, -1) / math.sqrt(self.head_dim)
scores = scores.masked_fill(self.mask[:T, :T] == 0, float('-inf'))
attn   = F.softmax(scores, dim=-1)
out    = attn @ V
```

---

## Model — Transformer Block

- **Pre-LayerNorm**: LayerNorm을 Attention/FF **앞**에 적용 (학습 안정성↑)
- **Residual Connection**: 입력을 그대로 더해 기울기 소실 방지

```python
class TransformerBlock(nn.Module):
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x + self.attn(self.ln1(x))   # Pre-LN + Residual (Attention)
        x = x + self.ff(self.ln2(x))     # Pre-LN + Residual (FeedForward)
        return x
```

- FeedForward: `Linear(d_model → d_ff) → GELU → Linear(d_ff → d_model)`

---

## Model — Autoregressive 생성

- **핵심 원리**: 토큰 1개 생성 = 1번의 forward pass
- 100 토큰 생성 = **100번의 forward pass**
- 매 스텝: 마지막 위치의 logits만 사용, 확률 샘플링

```python
def generate(self, idx, max_new_tokens):
    for _ in range(max_new_tokens):
        idx_cond  = idx[:, -self.context_len:]   # Context window 크롭
        logits, _ = self(idx_cond)                # 1번 forward pass
        next_logits = logits[:, -1, :]            # 마지막 위치만 사용
        probs       = F.softmax(next_logits, dim=-1)
        next_token  = torch.multinomial(probs, num_samples=1)
        idx = torch.cat([idx, next_token], dim=1) # 토큰 추가
    return idx
```

---

## Pretraining — 개념

- **목표**: 다음 토큰 예측 (Next-Token Prediction)
- **손실 함수**: Cross-Entropy Loss
- 입력 `x`와 정답 `y`는 1칸 shift된 동일 시퀀스

```
입력 x: [T, h, e, " ", q, u, i, c, k]
정답 y: [h, e, " ", q, u, i, c, k, " "]
```

- **Train/Val 분리**: 과적합 모니터링
- 대량 텍스트 → 언어의 문법·패턴·구조 학습

---

## Pretraining — 설정

```python
# Model Architecture
CONTEXT_LEN = 128
D_MODEL     = 64
N_LAYERS    = 2
N_HEADS     = 4
D_FF        = 256

# Training
BATCH_SIZE    = 64
LEARNING_RATE = 3e-4   # 사전학습: 높은 LR
MAX_EPOCHS    = 5      # 대규모 데이터 → 적은 에폭
VAL_RATIO     = 0.1
```

---

## Pretraining — 학습 루프

```python
# Training
for x, y in train_loader:
    optimizer.zero_grad()
    logits, loss = model(x, targets=y)          # Cross-Entropy 내부 계산
    loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
    optimizer.step()

# Validation
def evaluate(model, loader, device):
    model.eval()
    with torch.no_grad():
        for x, y in loader:
            _, loss = model(x, targets=y)
            total_loss += loss.item()
    model.train()
    return total_loss / count
```

- Gradient Clipping (`max_norm=1.0`): 기울기 폭발 방지

---

## Finetuning — 개념

- **Transfer Learning**: 사전학습 가중치를 이어받아 소규모 데이터로 적응
- 언어 패턴은 이미 학습됨 → **태스크 포맷**만 새로 학습

| | Pretraining | Finetuning |
|---|---|---|
| LR | 3e-4 | **1e-4** (낮게) |
| Epochs | 5 | **30** (많게) |
| Batch | 64 | **8** (작게) |
| Data | ~100K chars | **25 Q&A쌍** |

---

## Finetuning — 데이터 포맷

- Q&A 포맷을 반복 노출 → 모델이 패턴 학습

```python
def build_finetune_text(qa_pairs: list) -> str:
    parts = []
    for question, answer in qa_pairs:
        parts.append(f"\nQ: {question}\nA: {answer}\n")
    return "".join(parts)
```

결과:
```
Q: Who wrote Hamlet?
A: William Shakespeare

Q: What is the setting of Macbeth?
A: Scotland
```

---

## Finetuning — 학습 코드

```python
# 사전학습 체크포인트 로드
checkpoint = torch.load("checkpoints/pretrain_final.pt",
                        map_location=device, weights_only=True)
model = ToyGPT(**checkpoint['config']).to(device)
model.load_state_dict(checkpoint['model_state'])  # 가중치 이어받기

# 동일 학습 루프, 다른 하이퍼파라미터
optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)
for epoch in range(1, 31):
    for x, y in loader:
        optimizer.zero_grad()
        _, loss = model(x, targets=y)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
```

---

## Chat — Streaming 생성

- **실시간 출력**: 토큰 생성 즉시 `print(char, end='', flush=True)`
- ChatGPT의 스트리밍이 동작하는 원리와 동일

```python
def stream_generate(model, tokenizer, prompt, device,
                    temperature=0.8, top_k=40, max_new_tokens=200):
    ids     = tokenizer.encode(prompt)
    context = torch.tensor([ids], dtype=torch.long, device=device)

    for _ in range(max_new_tokens):
        context_crop = context[:, -model.context_len:]  # 윈도우 크롭
        logits, _    = model(context_crop)               # 1 forward pass
        next_logits  = logits[0, -1, :]                  # 마지막 토큰

        # ... (샘플링) ...

        char = tokenizer.decode([next_token.item()])
        print(char, end='', flush=True)                  # 즉시 출력
        context = torch.cat([context, next_token], dim=1)
```

---

## Chat — Temperature & Top-k 샘플링

- **Temperature**: logits 스케일 조정 → 낮을수록 보수적, 높을수록 다양
- **Top-k**: 상위 k개 토큰만 후보로 유지 → 저품질 토큰 차단

```python
# Temperature scaling
next_logits = next_logits / temperature   # < 1: 집중, > 1: 분산

# Top-k filtering
top_vals, _ = torch.topk(next_logits, min(top_k, next_logits.size(-1)))
threshold   = top_vals[-1]
next_logits = next_logits.masked_fill(
    next_logits < threshold, float('-inf')  # 하위 토큰 제거
)

# 최종 샘플링
probs      = torch.softmax(next_logits, dim=-1)
next_token = torch.multinomial(probs, num_samples=1)
```

---

## Summary — LLM Lifecycle

| 단계 | 파일 | 핵심 개념 | 목표 |
|---|---|---|---|
| **Tokenize** | `tokenizer.py` | 문자 → 정수 ID | 텍스트 수치화 |
| **Pretrain** | `01_pretrain.py` | Next-token prediction | 언어 패턴 학습 |
| **Finetune** | `02_finetune.py` | Transfer Learning | 태스크 적응 |
| **Chat** | `03_chat.py` | Streaming + Sampling | 배포 및 추론 |

- 전체 코드 ~300줄로 GPT 라이프사이클 완성
- 핵심 원리: **다음 토큰 예측** 하나로 언어 모델 전체를 설명 가능
