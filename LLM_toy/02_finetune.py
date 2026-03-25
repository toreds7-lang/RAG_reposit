"""
02_finetune.py — Stage 2: 파인튜닝 (Fine-tuning)

[목표]
  사전 학습된 모델에 셰익스피어 Q&A 지식을 주입합니다.
  "Q: ... A: ..." 형식으로 25개의 예시를 학습하면
  모델이 질문-답변 형식으로 응답하는 방법을 배웁니다.

[핵심 차이 — 사전 학습 vs 파인튜닝]
  사전 학습: 대량 텍스트, 높은 LR, 적은 epoch
  파인튜닝 : 소량 라벨 데이터, 낮은 LR, 많은 epoch

[실행]
  python 02_finetune.py   (먼저 01_pretrain.py를 실행해야 합니다)

[출력]
  - 학습 중: epoch마다 손실 및 샘플 생성
  - Before/After 비교: 파인튜닝 전후 응답 차이
  - checkpoints/finetune_final.pt
"""

import os
import time
import torch
from torch.utils.data import DataLoader

from tokenizer import CharTokenizer
from model import ToyGPT
from data import TextDataset


# ══════════════════════════════════════════════════════════════
# 하이퍼파라미터 설정
# ══════════════════════════════════════════════════════════════

LEARNING_RATE     = 1e-4    # 사전 학습보다 낮은 LR (기존 지식 보존)
MAX_EPOCHS        = 30      # 소량 데이터이므로 epoch 수를 늘림
BATCH_SIZE        = 8       # 소량 데이터에 맞게 작게 설정

PRETRAIN_CKPT     = "checkpoints/pretrain_final.pt"
TOKENIZER_PATH    = "checkpoints/tokenizer.json"
FINETUNE_CKPT     = "checkpoints/finetune_final.pt"

torch.manual_seed(42)


# ══════════════════════════════════════════════════════════════
# 파인튜닝 데이터 — 셰익스피어 Q&A 25쌍
# ══════════════════════════════════════════════════════════════
# 형식: "\nQ: {질문}\nA: {답변}\n"
# 이 형식으로 학습하면 모델은 "Q:" 다음에 "A:"로 답하는 패턴을 익힙니다.

QA_PAIRS = [
    ("Who wrote Romeo and Juliet?",
     "William Shakespeare wrote Romeo and Juliet around 1594."),
    ("What is the famous line from Hamlet?",
     "To be, or not to be, that is the question."),
    ("Who is Juliet's lover?",
     "Juliet's lover is Romeo, a young man from the Montague family."),
    ("What family does Romeo belong to?",
     "Romeo belongs to the Montague family, rivals of the Capulets."),
    ("What is the setting of Romeo and Juliet?",
     "Romeo and Juliet is set in Verona, Italy."),
    ("Who is Hamlet's father?",
     "Hamlet's father is King Hamlet, who was murdered by his brother Claudius."),
    ("What is Hamlet's tragic flaw?",
     "Hamlet's tragic flaw is his indecisiveness and inability to act quickly."),
    ("Who does Othello kill?",
     "Othello kills his wife Desdemona after being manipulated by Iago."),
    ("What is the main theme of Macbeth?",
     "The main themes of Macbeth are ambition, guilt, and the corrupting power of unchecked desire."),
    ("Who are the three witches in Macbeth?",
     "The three witches in Macbeth are supernatural beings who prophesy Macbeth's rise and fall."),
    ("What does Shylock demand in The Merchant of Venice?",
     "Shylock demands a pound of flesh as payment for his loan to Antonio."),
    ("Who is Prospero in The Tempest?",
     "Prospero is the rightful Duke of Milan who uses magic on an enchanted island."),
    ("What is a Shakespearean sonnet?",
     "A Shakespearean sonnet has 14 lines: three quatrains and a final couplet, with rhyme scheme ABAB CDCD EFEF GG."),
    ("How many plays did Shakespeare write?",
     "Shakespeare wrote approximately 37 plays, including tragedies, comedies, and histories."),
    ("Who is King Lear's faithful daughter?",
     "Cordelia is King Lear's faithful and loving daughter who refuses to flatter him falsely."),
    ("What causes the tragedy in Romeo and Juliet?",
     "The tragedy is caused by the long feud between the Montague and Capulet families."),
    ("Who is Puck in A Midsummer Night's Dream?",
     "Puck is a mischievous fairy and servant to Oberon who causes comic confusion with a love potion."),
    ("What is the meaning of 'All the world's a stage'?",
     "All the world's a stage means that life is like a play, and people are merely actors playing their parts."),
    ("Who kills Macbeth?",
     "Macduff kills Macbeth in the final battle, fulfilling the witches' prophecy."),
    ("What is the Globe Theatre?",
     "The Globe Theatre was Shakespeare's famous theatre in London, built in 1599."),
    ("Who is Iago in Othello?",
     "Iago is the villain of Othello, a scheming soldier who manipulates everyone around him."),
    ("What language did Shakespeare write in?",
     "Shakespeare wrote in Early Modern English, which differs from today's English but is still readable."),
    ("Who is Falstaff?",
     "Falstaff is a comic character in Henry IV and The Merry Wives of Windsor, known for his wit and cowardice."),
    ("What is a soliloquy?",
     "A soliloquy is a speech where a character speaks their thoughts aloud when alone on stage."),
    ("Why is Shakespeare important?",
     "Shakespeare is important because he profoundly influenced the English language and literature, creating timeless stories of human nature."),
]


def build_finetune_text(qa_pairs: list) -> str:
    """
    Q&A 쌍을 모델이 학습할 수 있는 텍스트 형식으로 변환합니다.

    각 쌍을 "\nQ: ...\nA: ...\n" 형식으로 이어 붙입니다.
    모델은 이 패턴을 반복 학습하여 Q: → A: 응답 방법을 익힙니다.
    """
    parts = []
    for question, answer in qa_pairs:
        parts.append(f"\nQ: {question}\nA: {answer}\n")
    return "".join(parts)


# ══════════════════════════════════════════════════════════════
# 메인 파인튜닝 루프
# ══════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("  Stage 2: 파인튜닝 (Fine-tuning)")
    print("=" * 60)

    # 사전 학습 체크포인트 존재 확인
    assert os.path.exists(PRETRAIN_CKPT), (
        f"\n오류: '{PRETRAIN_CKPT}'를 찾을 수 없습니다.\n"
        "먼저 01_pretrain.py를 실행하세요!"
    )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if device.type == 'cuda':
        print(f"\nGPU 감지: {torch.cuda.get_device_name(0)}")
    else:
        print("\nCPU 모드")
    print(f"사용 디바이스: {device}")

    # ── STEP 1: 사전 학습 체크포인트 & 토크나이저 로드 ─────────
    print("\n[STEP 1] 사전 학습 모델 로드 중...")
    checkpoint = torch.load(PRETRAIN_CKPT, map_location=device, weights_only=True)
    tokenizer  = CharTokenizer.load(TOKENIZER_PATH)
    config     = checkpoint['config']

    model = ToyGPT(**config).to(device)
    model.load_state_dict(checkpoint['model_state'])
    print(f"모델 로드 완료  |  파라미터: {model.count_parameters():,}")
    print(f"사전 학습 최종 손실: {checkpoint['train_losses'][-1]:.4f}")

    # ── STEP 2: 파인튜닝 데이터 준비 ────────────────────────────
    print("\n[STEP 2] 파인튜닝 데이터 준비 중...")
    finetune_text = build_finetune_text(QA_PAIRS)
    print(f"파인튜닝 텍스트 크기: {len(finetune_text):,} 문자")
    print(f"Q&A 쌍 수: {len(QA_PAIRS)}")

    # 알 수 없는 문자 필터링 (토크나이저 vocab에 없는 문자 제거)
    finetune_text = ''.join(ch for ch in finetune_text if ch in tokenizer.vocab)

    token_ids = tokenizer.encode(finetune_text)
    print(f"토큰 수: {len(token_ids):,}")

    context_len = config['context_len']
    dataset     = TextDataset(token_ids, context_len)
    use_pin     = device.type == 'cuda'
    loader      = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True, pin_memory=use_pin)

    # ── STEP 3: Before (파인튜닝 전) 응답 저장 ──────────────────
    test_prompt = "\nQ: Who is Romeo?\nA:"
    print(f"\n[Before 파인튜닝] 프롬프트: {repr(test_prompt)}")
    model.eval()
    with torch.no_grad():
        seed_ids = tokenizer.encode(test_prompt)
        seed_tensor = torch.tensor([seed_ids], dtype=torch.long, device=device)
        before_ids = model.generate(seed_tensor, max_new_tokens=100, temperature=0.8, top_k=40)
    before_text = tokenizer.decode(before_ids[0].tolist())
    print(f"Before: {before_text[len(test_prompt):][:150]}")

    # ── STEP 4: 파인튜닝 학습 루프 ──────────────────────────────
    print("\n[STEP 3] 파인튜닝 시작!")
    print("-" * 60)

    optimizer    = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE)
    train_losses = []
    start_time   = time.time()

    model.train()
    for epoch in range(1, MAX_EPOCHS + 1):
        epoch_loss = 0.0
        n_batches  = 0

        for i, (x, y) in enumerate(loader):
            x, y = x.to(device), y.to(device)
            optimizer.zero_grad()
            _, loss = model(x, targets=y)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            epoch_loss += loss.item()
            n_batches  += 1

            print(
                f"\rEpoch {epoch}/{MAX_EPOCHS} | "
                f"Batch {i+1}/{len(loader)} | "
                f"Loss: {loss.item():.4f}",
                end='', flush=True
            )

        avg_loss = epoch_loss / n_batches
        train_losses.append(avg_loss)
        elapsed = time.time() - start_time
        print(f"\nEpoch {epoch}/{MAX_EPOCHS} | 평균 손실: {avg_loss:.4f} | 경과: {elapsed:.1f}s")

        if device.type == 'cuda':
            mem = torch.cuda.memory_allocated() / 1e6
            print(f"  GPU 메모리 사용: {mem:.1f} MB")

        # 5 epoch마다 샘플 생성으로 학습 진행 확인
        if epoch % 5 == 0:
            model.eval()
            with torch.no_grad():
                sample_ids = model.generate(
                    seed_tensor, max_new_tokens=100, temperature=0.8, top_k=40
                )
            sample_text = tokenizer.decode(sample_ids[0].tolist())
            print(f"  샘플: ...{sample_text[len(test_prompt):][:100]}")
            model.train()

    total_time = time.time() - start_time
    print(f"\n총 파인튜닝 시간: {total_time:.1f}초")

    # ── STEP 5: After (파인튜닝 후) 응답 생성 ───────────────────
    print("\n" + "=" * 60)
    print("  [Before vs After 비교]")
    print("=" * 60)
    print(f"프롬프트: {repr(test_prompt)}\n")

    model.eval()
    with torch.no_grad():
        after_ids = model.generate(seed_tensor, max_new_tokens=150, temperature=0.8, top_k=40)
    after_text = tokenizer.decode(after_ids[0].tolist())

    print("[ Before 파인튜닝 ]")
    print(before_text[len(test_prompt):][:200])
    print()
    print("[ After 파인튜닝 ]")
    print(after_text[len(test_prompt):][:200])
    print("=" * 60)

    # ── STEP 6: 체크포인트 저장 ─────────────────────────────────
    print(f"\n[STEP 5] 체크포인트 저장 중...")
    torch.save({
        'model_state' : model.state_dict(),
        'config'      : config,
        'train_losses': train_losses,
        'epoch'       : MAX_EPOCHS,
    }, FINETUNE_CKPT)
    print(f"체크포인트 저장됨: {FINETUNE_CKPT}")

    print("\n" + "=" * 60)
    print("  파인튜닝 완료!")
    print("\n  다음 단계: python 03_chat.py")
    print("=" * 60)


if __name__ == '__main__':
    main()
