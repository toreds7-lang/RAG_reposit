"""
model.py — ToyGPT: 강의용 미니 GPT 모델

구조 (GPT-2 논문과 동일한 아키텍처):

  입력 토큰 ids
      ↓
  Token Embedding  +  Position Embedding
      ↓
  TransformerBlock × n_layers
  (각 블록 = CausalSelfAttention + FeedForward + LayerNorm × 2)
      ↓
  LayerNorm (최종)
      ↓
  LM Head (Linear, weight tying)
      ↓
  logits → (softmax) → 다음 토큰 확률

[핵심 개념]
  - Causal Mask: 미래 토큰을 볼 수 없게 하는 삼각형 마스크
  - Weight Tying: Embedding과 LM Head의 가중치를 공유 → 파라미터 절약
  - Autoregressive: 토큰을 하나씩 생성 (generate 메서드 참고)
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F


# ══════════════════════════════════════════════════════════════
# 1. Causal Self-Attention (인과적 자기 주의)
# ══════════════════════════════════════════════════════════════

class CausalSelfAttention(nn.Module):
    """
    마스킹된 멀티헤드 셀프 어텐션.

    "Attention is All You Need" (Vaswani et al., 2017)의 핵심:
        Attention(Q, K, V) = softmax(Q @ K^T / sqrt(d_k)) @ V

    Causal(인과적): 현재 위치 t는 t 이전 토큰만 볼 수 있습니다.
    이를 위해 미래 위치를 -inf로 마스킹합니다.
    """

    def __init__(self, d_model: int, n_heads: int, context_len: int, dropout: float):
        super().__init__()
        assert d_model % n_heads == 0, "d_model은 n_heads로 나누어져야 합니다."

        self.n_heads = n_heads
        self.d_head = d_model // n_heads  # 헤드당 차원

        # Q, K, V를 한 번에 계산하는 행렬 (효율적)
        self.qkv_proj = nn.Linear(d_model, 3 * d_model, bias=False)
        # 멀티헤드 결과를 합치는 출력 행렬
        self.out_proj = nn.Linear(d_model, d_model, bias=False)

        self.attn_dropout = nn.Dropout(dropout)
        self.resid_dropout = nn.Dropout(dropout)

        # Causal Mask: 하삼각행렬 (미래 토큰 → -inf)
        # register_buffer: 학습 파라미터가 아니지만 체크포인트에 저장됨
        mask = torch.tril(torch.ones(context_len, context_len))
        self.register_buffer('mask', mask)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B, T, C = x.shape  # (배치, 시퀀스 길이, d_model)

        # ── Q, K, V 계산 ──────────────────────────────────────
        qkv = self.qkv_proj(x)                          # (B, T, 3*C)
        Q, K, V = qkv.split(C, dim=-1)                  # 각각 (B, T, C)

        # 멀티헤드: (B, T, C) → (B, n_heads, T, d_head)
        def split_heads(t):
            return t.view(B, T, self.n_heads, self.d_head).transpose(1, 2)

        Q, K, V = split_heads(Q), split_heads(K), split_heads(V)

        # ── Scaled Dot-Product Attention ───────────────────────
        # 스케일링: d_head의 제곱근으로 나눠 gradient 안정화
        scale = math.sqrt(self.d_head)
        scores = (Q @ K.transpose(-2, -1)) / scale      # (B, H, T, T)

        # Causal Masking: 미래 위치를 매우 작은 값으로 → softmax 후 0이 됨
        scores = scores.masked_fill(
            self.mask[:T, :T] == 0,
            float('-inf')
        )

        attn_weights = F.softmax(scores, dim=-1)         # (B, H, T, T)
        attn_weights = self.attn_dropout(attn_weights)

        # ── V와 결합 ────────────────────────────────────────────
        out = attn_weights @ V                           # (B, H, T, d_head)
        out = out.transpose(1, 2).contiguous().view(B, T, C)  # 헤드 합치기
        out = self.resid_dropout(self.out_proj(out))
        return out


# ══════════════════════════════════════════════════════════════
# 2. Feed-Forward Network (피드포워드 네트워크)
# ══════════════════════════════════════════════════════════════

class FeedForward(nn.Module):
    """
    2층 MLP with GELU 활성화.

    각 토큰을 독립적으로 처리합니다 (position-wise).
    d_ff는 보통 d_model의 4배 (논문 관례).
    """

    def __init__(self, d_model: int, d_ff: int, dropout: float):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(d_model, d_ff),
            nn.GELU(),          # ReLU보다 부드러운 활성화 함수 (GPT-2 사용)
            nn.Linear(d_ff, d_model),
            nn.Dropout(dropout),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


# ══════════════════════════════════════════════════════════════
# 3. Transformer Block (트랜스포머 블록)
# ══════════════════════════════════════════════════════════════

class TransformerBlock(nn.Module):
    """
    Pre-LayerNorm Transformer 블록 (GPT-2 스타일).

    Pre-LN 구조 (GPT-2):         Post-LN 구조 (원논문):
        x → LN → Attn → + x         x → Attn → + x → LN
        x → LN → FF  → + x          x → FF  → + x → LN

    Pre-LN이 학습이 더 안정적입니다.
    """

    def __init__(self, d_model: int, n_heads: int, d_ff: int,
                 context_len: int, dropout: float):
        super().__init__()
        self.ln1 = nn.LayerNorm(d_model)
        self.attn = CausalSelfAttention(d_model, n_heads, context_len, dropout)
        self.ln2 = nn.LayerNorm(d_model)
        self.ff = FeedForward(d_model, d_ff, dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Residual Connection (잔차 연결): 그래디언트 흐름 보장
        x = x + self.attn(self.ln1(x))
        x = x + self.ff(self.ln2(x))
        return x


# ══════════════════════════════════════════════════════════════
# 4. ToyGPT — 전체 모델
# ══════════════════════════════════════════════════════════════

class ToyGPT(nn.Module):
    """
    강의용 미니 GPT 언어 모델.

    기본 설정 (CPU에서 2-3분 학습):
        vocab_size  : ~70 (문자 단위)
        context_len : 128
        d_model     : 64
        n_layers    : 2
        n_heads     : 4
        d_ff        : 256
        → 총 파라미터: ~200K
    """

    def __init__(
        self,
        vocab_size: int,
        context_len: int = 128,
        d_model: int = 64,
        n_layers: int = 2,
        n_heads: int = 4,
        d_ff: int = 256,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.context_len = context_len

        # ── 임베딩 레이어 ───────────────────────────────────────
        # 토큰 임베딩: 각 정수 ID → d_model 차원 벡터
        self.token_embedding = nn.Embedding(vocab_size, d_model)
        # 위치 임베딩: 각 위치(0~context_len) → d_model 차원 벡터
        self.position_embedding = nn.Embedding(context_len, d_model)

        self.drop = nn.Dropout(dropout)

        # ── Transformer 블록 스택 ────────────────────────────────
        self.blocks = nn.ModuleList([
            TransformerBlock(d_model, n_heads, d_ff, context_len, dropout)
            for _ in range(n_layers)
        ])

        self.ln_final = nn.LayerNorm(d_model)

        # ── LM Head (언어 모델 헤드) ────────────────────────────
        # d_model → vocab_size: 각 위치에서 다음 토큰의 확률 예측
        self.lm_head = nn.Linear(d_model, vocab_size, bias=False)

        # Weight Tying: 입력 임베딩과 출력 행렬을 공유
        # → 같은 토큰이 입력과 출력에서 유사한 표현을 가져야 한다는 직관
        self.lm_head.weight = self.token_embedding.weight

        # 가중치 초기화 (GPT-2 스타일)
        self.apply(self._init_weights)

    def _init_weights(self, module):
        """가중치 초기화: Linear → 표준편차 0.02 정규분포"""
        if isinstance(module, nn.Linear):
            nn.init.normal_(module.weight, mean=0.0, std=0.02)
            if module.bias is not None:
                nn.init.zeros_(module.bias)
        elif isinstance(module, nn.Embedding):
            nn.init.normal_(module.weight, mean=0.0, std=0.02)

    def count_parameters(self) -> int:
        """학습 가능한 파라미터 수를 반환합니다."""
        return sum(p.numel() for p in self.parameters() if p.requires_grad)

    def forward(
        self,
        idx: torch.Tensor,
        targets: torch.Tensor = None,
    ):
        """
        순전파.

        Args:
            idx    : (B, T) — 입력 토큰 ID
            targets: (B, T) — 정답 토큰 ID (학습 시), 없으면 None

        Returns:
            logits : (B, T, vocab_size) — 각 위치의 다음 토큰 로짓
            loss   : CrossEntropy 손실 (targets가 None이면 None)
        """
        B, T = idx.shape
        assert T <= self.context_len, \
            f"시퀀스 길이 {T}가 context_len {self.context_len}을 초과합니다."

        # 위치 ID: [0, 1, 2, ..., T-1]
        positions = torch.arange(T, device=idx.device)

        # 토큰 임베딩 + 위치 임베딩 합산
        x = self.drop(
            self.token_embedding(idx) + self.position_embedding(positions)
        )  # (B, T, d_model)

        # Transformer 블록 순차 통과
        for block in self.blocks:
            x = block(x)

        x = self.ln_final(x)                            # (B, T, d_model)
        logits = self.lm_head(x)                         # (B, T, vocab_size)

        # 손실 계산 (학습 모드)
        loss = None
        if targets is not None:
            # (B, T, vocab_size) → (B*T, vocab_size) 로 reshape 후 CrossEntropy
            loss = F.cross_entropy(
                logits.view(-1, logits.size(-1)),
                targets.view(-1),
            )

        return logits, loss

    @torch.no_grad()
    def generate(
        self,
        idx: torch.Tensor,
        max_new_tokens: int,
        temperature: float = 1.0,
        top_k: int = 40,
    ) -> torch.Tensor:
        """
        자기회귀적(autoregressive) 토큰 생성.

        핵심: 토큰을 하나씩 생성하며, 매번 새로운 forward pass를 수행합니다.
        이것이 GPT의 실제 동작 방식입니다.

        Args:
            idx           : (1, T) — 시드(seed) 토큰
            max_new_tokens: 생성할 최대 토큰 수
            temperature   : 높을수록 다양한 출력 (기본 1.0)
            top_k         : 상위 k개 토큰 중에서만 샘플링

        Returns:
            (1, T + max_new_tokens) — 확장된 토큰 시퀀스
        """
        self.eval()
        for _ in range(max_new_tokens):
            # context_len 초과 시 오른쪽 잘라냄
            idx_cond = idx[:, -self.context_len:]

            # 순전파: 마지막 위치의 logits만 사용
            logits, _ = self(idx_cond)
            next_logits = logits[:, -1, :]              # (1, vocab_size)

            # Temperature 스케일링
            next_logits = next_logits / temperature

            # Top-k 필터링: 상위 k개 외의 토큰을 -inf로 설정
            if top_k is not None:
                top_vals, _ = torch.topk(next_logits, min(top_k, next_logits.size(-1)))
                threshold = top_vals[:, -1].unsqueeze(-1)
                next_logits = next_logits.masked_fill(next_logits < threshold, float('-inf'))

            # 확률 분포에서 샘플링
            probs = F.softmax(next_logits, dim=-1)
            next_token = torch.multinomial(probs, num_samples=1)  # (1, 1)

            # 생성된 토큰을 시퀀스에 추가
            idx = torch.cat([idx, next_token], dim=1)

        return idx


# ──────────────────────────────────────────────
# 실행 시 모델 구조 및 파라미터 수 출력
# ──────────────────────────────────────────────
if __name__ == '__main__':
    model = ToyGPT(vocab_size=70)
    print(model)
    print(f"\n총 파라미터 수: {model.count_parameters():,}")

    # 더미 입력으로 동작 확인
    dummy_input = torch.randint(0, 70, (2, 32))   # (batch=2, seq=32)
    dummy_target = torch.randint(0, 70, (2, 32))
    logits, loss = model(dummy_input, targets=dummy_target)
    print(f"logits shape : {logits.shape}")        # (2, 32, 70)
    print(f"loss         : {loss.item():.4f}")
