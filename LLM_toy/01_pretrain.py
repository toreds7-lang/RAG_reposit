"""
01_pretrain.py — Stage 1: 사전 학습 (Pre-training)

[목표]
  아무것도 모르는 모델을 셰익스피어 텍스트로 학습시킵니다.
  모델은 "이전 문자들이 주어졌을 때 다음 문자를 예측"하는 방식으로 학습합니다.
  이것이 GPT, Claude 등 모든 대형 언어 모델의 기본 학습 방식입니다.

[실행]
  python 01_pretrain.py

[출력]
  - 매 epoch마다: 학습 손실, 검증 손실, 생성 샘플 텍스트
  - 완료 후: checkpoints/pretrain_final.pt, checkpoints/tokenizer.json
  - 손실 그래프: loss_curve.png

[소요 시간]
  CPU 기준 약 2~3분 (n_layers=2, d_model=64 기준)
"""

import os
import time
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, random_split
import matplotlib.pyplot as plt

from tokenizer import CharTokenizer
from model import ToyGPT
from data import TextDataset, get_shakespeare


# ══════════════════════════════════════════════════════════════
# 하이퍼파라미터 설정 (모든 설정을 한 곳에 모아 쉽게 조정 가능)
# ══════════════════════════════════════════════════════════════

# 모델 구조
CONTEXT_LEN = 128   # 한 번에 볼 수 있는 최대 토큰(문자) 수
D_MODEL     = 64    # 임베딩 차원 (클수록 표현력 ↑, 속도 ↓)
N_LAYERS    = 2     # Transformer 블록 수
N_HEADS     = 4     # 멀티헤드 어텐션의 헤드 수
D_FF        = 256   # FeedForward 은닉층 차원 (보통 D_MODEL × 4)
DROPOUT     = 0.1   # 드롭아웃 비율 (과적합 방지)

# 학습 설정
BATCH_SIZE    = 64      # 한 번에 처리할 샘플 수
LEARNING_RATE = 3e-4    # AdamW 학습률
MAX_EPOCHS    = 5       # 전체 데이터를 몇 번 반복할지
VAL_RATIO     = 0.1     # 검증 데이터 비율 (전체의 10%)

# 경로
CHECKPOINT_DIR  = "checkpoints"
CHECKPOINT_PATH = os.path.join(CHECKPOINT_DIR, "pretrain_final.pt")
TOKENIZER_PATH  = os.path.join(CHECKPOINT_DIR, "tokenizer.json")
LOSS_CURVE_PATH = "loss_curve.png"

# 시드 고정 (재현성)
torch.manual_seed(42)


# ══════════════════════════════════════════════════════════════
# 유틸리티 함수
# ══════════════════════════════════════════════════════════════

def evaluate(model, loader, device):
    """검증 데이터셋에서 평균 손실을 계산합니다."""
    model.eval()
    total_loss = 0.0
    count = 0
    with torch.no_grad():
        for x, y in loader:
            x, y = x.to(device), y.to(device)
            _, loss = model(x, targets=y)
            total_loss += loss.item()
            count += 1
    model.train()
    return total_loss / count if count > 0 else float('inf')


def generate_sample(model, tokenizer, device, seed_text="ROMEO:", max_tokens=200):
    """모델이 현재 학습된 정도를 보여주는 샘플 텍스트를 생성합니다."""
    model.eval()
    ids = tokenizer.encode(seed_text)
    idx = torch.tensor([ids], dtype=torch.long, device=device)
    output_ids = model.generate(idx, max_new_tokens=max_tokens, temperature=0.8, top_k=40)
    model.train()
    return tokenizer.decode(output_ids[0].tolist())


# ══════════════════════════════════════════════════════════════
# 메인 학습 루프
# ══════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("  Stage 1: 사전 학습 (Pre-training)")
    print("=" * 60)

    # ── 디바이스 설정 ────────────────────────────────────────
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if device.type == 'cuda':
        print(f"\nGPU 감지: {torch.cuda.get_device_name(0)}")
        print(f"GPU 메모리: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
    else:
        print("\nCPU 모드 (GPU 없음)")
    print(f"사용 디바이스: {device}")

    # ── STEP 1: 데이터 준비 ──────────────────────────────────
    print("\n[STEP 1] 데이터 준비 중...")
    text = get_shakespeare()
    print(f"텍스트 크기: {len(text):,} 문자")

    # 토크나이저 생성 및 저장
    tokenizer = CharTokenizer(text)
    os.makedirs(CHECKPOINT_DIR, exist_ok=True)
    tokenizer.save(TOKENIZER_PATH)
    print(f"어휘 크기 (vocab_size): {tokenizer.vocab_size}")

    # 전체 텍스트를 정수 시퀀스로 변환
    token_ids = tokenizer.encode(text)
    print(f"총 토큰 수: {len(token_ids):,}")

    # Train / Val 분리
    full_dataset = TextDataset(token_ids, CONTEXT_LEN)
    val_size   = int(len(full_dataset) * VAL_RATIO)
    train_size = len(full_dataset) - val_size
    train_ds, val_ds = random_split(full_dataset, [train_size, val_size])

    use_pin      = device.type == 'cuda'
    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True,  pin_memory=use_pin)
    val_loader   = DataLoader(val_ds,   batch_size=BATCH_SIZE, shuffle=False, pin_memory=use_pin)

    print(f"학습 샘플: {train_size:,}  |  검증 샘플: {val_size:,}")

    # ── STEP 2: 모델 초기화 ──────────────────────────────────
    print("\n[STEP 2] 모델 초기화 중...")
    model = ToyGPT(
        vocab_size  = tokenizer.vocab_size,
        context_len = CONTEXT_LEN,
        d_model     = D_MODEL,
        n_layers    = N_LAYERS,
        n_heads     = N_HEADS,
        d_ff        = D_FF,
        dropout     = DROPOUT,
    ).to(device)

    print(f"총 파라미터 수: {model.count_parameters():,}")

    optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE)

    # ── STEP 3: 학습 루프 ────────────────────────────────────
    print("\n[STEP 3] 학습 시작!")
    print("-" * 60)

    train_losses = []
    val_losses   = []
    start_time   = time.time()

    for epoch in range(1, MAX_EPOCHS + 1):
        epoch_loss = 0.0
        n_batches  = 0

        for i, (x, y) in enumerate(train_loader):
            x, y = x.to(device), y.to(device)

            optimizer.zero_grad()
            logits, loss = model(x, targets=y)
            loss.backward()

            # Gradient Clipping: 폭발적 그래디언트 방지
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)

            optimizer.step()

            epoch_loss += loss.item()
            n_batches  += 1

            # 진행 상황 출력 (tqdm 미사용 — 강의 환경 호환)
            print(
                f"\rEpoch {epoch}/{MAX_EPOCHS} | "
                f"Batch {i+1}/{len(train_loader)} | "
                f"Loss: {loss.item():.4f}",
                end='', flush=True
            )

        # epoch 평균 손실 및 검증 손실
        avg_train_loss = epoch_loss / n_batches
        avg_val_loss   = evaluate(model, val_loader, device)
        elapsed        = time.time() - start_time

        train_losses.append(avg_train_loss)
        val_losses.append(avg_val_loss)

        print(f"\nEpoch {epoch}/{MAX_EPOCHS} 완료 | "
              f"학습 손실: {avg_train_loss:.4f} | "
              f"검증 손실: {avg_val_loss:.4f} | "
              f"경과: {elapsed:.1f}s")

        if device.type == 'cuda':
            mem = torch.cuda.memory_allocated() / 1e6
            print(f"  GPU 메모리 사용: {mem:.1f} MB")

        # 현재 모델이 생성하는 샘플 텍스트 출력 (학습 진행 확인)
        sample = generate_sample(model, tokenizer, device)
        print(f"\n--- 생성 샘플 (Epoch {epoch}) ---")
        print(sample[:300])
        print("-" * 60)

    total_time = time.time() - start_time
    print(f"\n총 학습 시간: {total_time:.1f}초 ({total_time/60:.1f}분)")

    # ── STEP 4: 손실 그래프 저장 ────────────────────────────
    print(f"\n[STEP 4] 손실 그래프 저장 중...")
    plt.figure(figsize=(10, 4))
    plt.plot(range(1, MAX_EPOCHS + 1), train_losses, 'b-o', label='학습 손실 (Train Loss)')
    plt.plot(range(1, MAX_EPOCHS + 1), val_losses,   'r-o', label='검증 손실 (Val Loss)')
    plt.xlabel('Epoch')
    plt.ylabel('Loss (Cross-Entropy)')
    plt.title('사전 학습 손실 곡선 (Pre-training Loss Curve)')
    plt.legend()
    plt.tight_layout()
    plt.savefig(LOSS_CURVE_PATH, dpi=120)
    try:
        plt.show()
    except Exception:
        pass  # headless 환경에서는 무시
    plt.close()
    print(f"손실 그래프 저장됨: {LOSS_CURVE_PATH}")

    # ── STEP 5: 체크포인트 저장 ─────────────────────────────
    print(f"\n[STEP 5] 체크포인트 저장 중...")
    checkpoint = {
        'model_state': model.state_dict(),
        'config': {
            'vocab_size' : tokenizer.vocab_size,
            'context_len': CONTEXT_LEN,
            'd_model'    : D_MODEL,
            'n_layers'   : N_LAYERS,
            'n_heads'    : N_HEADS,
            'd_ff'       : D_FF,
            'dropout'    : DROPOUT,
        },
        'train_losses': train_losses,
        'val_losses'  : val_losses,
        'epoch'       : MAX_EPOCHS,
    }
    torch.save(checkpoint, CHECKPOINT_PATH)
    print(f"체크포인트 저장됨: {CHECKPOINT_PATH}")

    print("\n" + "=" * 60)
    print("  사전 학습 완료!")
    print(f"  최종 학습 손실: {train_losses[-1]:.4f}")
    print(f"  최종 검증 손실: {val_losses[-1]:.4f}")
    print("\n  다음 단계: python 02_finetune.py")
    print("=" * 60)


if __name__ == '__main__':
    main()
