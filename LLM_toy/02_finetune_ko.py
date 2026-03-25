"""
02_finetune_ko.py — Stage 2 (한국어): 한국어 파인튜닝

[목표]
  한국어로 사전 학습된 모델에 Q&A 형식을 학습시킵니다.
  질문(Q:)이 주어지면 답변(A:)을 생성하도록 적응시킵니다.

[실행]
  python 02_finetune_ko.py   (먼저 01_pretrain_ko.py를 실행해야 합니다)

[출력]
  - Before/After 비교: 파인튜닝 전후 응답 차이
  - checkpoints/finetune_ko_final.pt
"""

import os
import time
import torch
from torch.utils.data import DataLoader

from tokenizer import CharTokenizer
from model import ToyGPT
from data import TextDataset


# ══════════════════════════════════════════════════════════════
# 하이퍼파라미터
# ══════════════════════════════════════════════════════════════

LEARNING_RATE  = 1e-4
MAX_EPOCHS     = 40
BATCH_SIZE     = 8

PRETRAIN_CKPT  = "checkpoints/pretrain_ko_final.pt"
TOKENIZER_PATH = "checkpoints/tokenizer_ko.json"
FINETUNE_CKPT  = "checkpoints/finetune_ko_final.pt"

torch.manual_seed(42)


# ══════════════════════════════════════════════════════════════
# 한국어 Q&A 파인튜닝 데이터 (25쌍)
# 주제: 한국 역사, 문화, 전래동화 (사전 학습 텍스트와 연관)
# ══════════════════════════════════════════════════════════════

QA_PAIRS_KO = [
    # 전래동화
    ("흥부와 놀부 이야기에서 흥부는 어떤 사람인가요?",
     "흥부는 마음씨가 착하고 부지런한 사람입니다. 가난하게 살면서도 착한 마음을 잃지 않았습니다."),

    ("흥부가 부자가 된 이유는 무엇인가요?",
     "흥부가 다리 부러진 제비를 고쳐 주었고, 이듬해 봄 제비가 박씨를 물어다 주었습니다. 박 안에서 금은보화가 나왔습니다."),

    ("놀부는 왜 벌을 받았나요?",
     "놀부는 욕심에 일부러 제비 다리를 부러뜨렸습니다. 그 결과 박 안에서 도깨비들이 나와 놀부를 혼내 주었습니다."),

    ("토끼와 거북이 이야기의 교훈은 무엇인가요?",
     "꾸준함이 빠름을 이긴다는 교훈입니다. 자만하지 말고 끝까지 최선을 다해야 합니다."),

    ("금도끼 은도끼 이야기에서 나무꾼은 왜 상을 받았나요?",
     "나무꾼이 금도끼와 은도끼를 자신의 것이 아니라고 말한 정직함 때문입니다. 산신령이 정직함을 칭찬하여 세 도끼를 모두 주었습니다."),

    ("심청이는 왜 인당수에 몸을 던졌나요?",
     "눈 먼 아버지의 눈을 뜨게 하기 위해 공양미 삼백 석에 자신의 몸을 팔았습니다. 아버지를 위한 지극한 효심 때문입니다."),

    ("콩쥐팥쥐 이야기에서 콩쥐는 어떤 어려움을 겪었나요?",
     "친엄마를 잃고 계모와 의붓언니 팥쥐와 살았습니다. 계모는 콩쥐를 구박하고 힘든 일만 시켰습니다."),

    ("단군 이야기에서 웅녀는 어떻게 사람이 되었나요?",
     "환웅이 준 쑥과 마늘을 먹으며 백 일 동안 햇빛을 보지 않아야 했습니다. 곰이 인내하며 버텨 아름다운 여자 웅녀가 되었습니다."),

    # 한국 역사와 문화
    ("한글을 만든 사람은 누구인가요?",
     "한글은 조선 시대 세종대왕이 집현전 학자들과 함께 만들었습니다. 1443년에 훈민정음으로 완성되었습니다."),

    ("세종대왕은 왜 한글을 만들었나요?",
     "당시 우리말을 표현할 고유한 글자가 없어 백성들이 어려움을 겪었습니다. 세종대왕은 백성을 사랑하는 마음으로 한글을 만들었습니다."),

    ("이순신 장군은 어떤 업적을 남겼나요?",
     "임진왜란 때 거북선을 이용하여 왜군을 물리쳤습니다. 명량 해전, 한산도 대첩 등 수많은 전투에서 승리하여 나라를 구했습니다."),

    ("거북선은 무엇인가요?",
     "이순신 장군이 만든 배로 세계 최초의 철갑선으로 알려져 있습니다. 임진왜란 때 왜군을 물리치는 데 큰 역할을 하였습니다."),

    ("한국의 전통 명절은 무엇이 있나요?",
     "설날과 추석이 대표적인 전통 명절입니다. 설날에는 세배를 하고, 추석에는 강강술래를 하며 송편을 만들어 먹습니다."),

    ("한복은 무엇인가요?",
     "한복은 한국의 전통 의상입니다. 색깔이 아름답고 형태가 우아하여 명절이나 특별한 날에 입습니다."),

    ("김치는 어떤 음식인가요?",
     "김치는 배추나 무를 소금에 절여 양념하여 발효시킨 한국 전통 음식입니다. 한국인이 가장 즐겨 먹는 음식 중 하나입니다."),

    ("비빔밥은 어떻게 만드나요?",
     "밥 위에 여러 가지 나물과 고기, 달걀을 올려 고추장과 함께 비벼 먹는 음식입니다. 영양이 풍부하고 맛이 좋습니다."),

    # 속담과 지혜
    ("가는 말이 고와야 오는 말이 곱다는 속담은 무슨 뜻인가요?",
     "남에게 좋게 대해야 나도 좋은 대우를 받는다는 뜻입니다. 말과 행동을 바르게 해야 한다는 교훈을 담고 있습니다."),

    ("백지장도 맞들면 낫다는 속담의 의미는 무엇인가요?",
     "어떤 일이든 혼자 하는 것보다 여럿이 함께 하면 더 쉽다는 뜻입니다. 협력의 중요성을 강조하는 속담입니다."),

    ("티끌 모아 태산이라는 말은 무슨 뜻인가요?",
     "작은 것이라도 꾸준히 모으면 큰 것이 된다는 뜻입니다. 작은 노력도 소홀히 하지 말라는 교훈입니다."),

    ("세 살 버릇 여든까지 간다는 속담의 교훈은 무엇인가요?",
     "어릴 때 몸에 밴 버릇은 나이가 들어도 잘 고쳐지지 않습니다. 어릴 때부터 좋은 습관을 길러야 한다는 뜻입니다."),

    # 자연과 계절
    ("한국의 봄 풍경은 어떤가요?",
     "진달래, 개나리, 벚꽃이 차례로 피어 아름다운 봄 풍경을 만들어 냅니다. 아이들은 들판에서 뛰어 놀고 어른들은 꽃놀이를 즐깁니다."),

    ("한국의 가을 풍경을 설명해 주세요.",
     "나뭇잎이 빨갛고 노랗게 물듭니다. 들판에는 황금빛 벼가 익어가고, 사람들은 단풍 구경을 나갑니다."),

    ("단군 신화에서 고조선은 누가 세웠나요?",
     "웅녀와 환웅의 아들 단군이 고조선을 세웠습니다. 단군은 우리 민족의 시조로 여겨집니다."),

    ("해님과 달님이 된 오누이 이야기에서 오누이는 어떻게 위기를 벗어났나요?",
     "호랑이가 쫓아오자 하늘에 기도하였습니다. 하늘에서 새 동아줄이 내려와 오누이는 하늘로 올라갔습니다. 오빠는 해님, 누이는 달님이 되었습니다."),

    ("한국의 전통 음악을 무엇이라고 부르나요?",
     "한국의 전통 음악은 국악이라고 합니다. 가야금, 거문고, 해금 등의 악기를 사용하여 연주합니다."),
]


def build_finetune_text(qa_pairs: list) -> str:
    """Q&A 쌍을 학습용 텍스트 형식으로 변환합니다."""
    parts = []
    for question, answer in qa_pairs:
        parts.append(f"\nQ: {question}\nA: {answer}\n")
    return "".join(parts)


# ══════════════════════════════════════════════════════════════
# 메인 파인튜닝 루프
# ══════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("  Stage 2 (한국어): 파인튜닝 (Fine-tuning)")
    print("=" * 60)

    assert os.path.exists(PRETRAIN_CKPT), (
        f"\n오류: '{PRETRAIN_CKPT}'를 찾을 수 없습니다.\n"
        "먼저 01_pretrain_ko.py를 실행하세요!"
    )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if device.type == 'cuda':
        print(f"GPU: {torch.cuda.get_device_name(0)}")
    else:
        print("CPU 모드")

    # ── STEP 1: 체크포인트 & 토크나이저 로드 ────────────────
    print("\n[STEP 1] 사전 학습 모델 로드 중...")
    checkpoint = torch.load(PRETRAIN_CKPT, map_location=device, weights_only=True)
    tokenizer  = CharTokenizer.load(TOKENIZER_PATH)
    config     = checkpoint['config']

    model = ToyGPT(**config).to(device)
    model.load_state_dict(checkpoint['model_state'])
    print(f"모델 로드 완료  |  파라미터: {model.count_parameters():,}")

    # ── STEP 2: 파인튜닝 데이터 준비 ────────────────────────
    print("\n[STEP 2] 파인튜닝 데이터 준비 중...")
    finetune_text = build_finetune_text(QA_PAIRS_KO)

    # vocab에 없는 문자 필터링 (한국어 tokenizer라 한글 대부분 포함됨)
    original_len  = len(finetune_text)
    finetune_text = ''.join(ch for ch in finetune_text if ch in tokenizer.vocab)
    filtered = original_len - len(finetune_text)
    if filtered > 0:
        print(f"필터링된 문자: {filtered}개 (vocab 밖의 문자)")

    print(f"파인튜닝 텍스트 크기: {len(finetune_text):,} 문자  |  Q&A 쌍: {len(QA_PAIRS_KO)}")

    token_ids   = tokenizer.encode(finetune_text)
    context_len = config['context_len']
    dataset     = TextDataset(token_ids, context_len)

    use_pin  = device.type == 'cuda'
    loader   = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True, pin_memory=use_pin)

    # ── STEP 3: Before (파인튜닝 전) 응답 저장 ──────────────
    test_prompt = "\nQ: 흥부와 놀부에서 흥부는 어떤 사람인가요?\nA:"
    seed_ids    = tokenizer.encode(test_prompt)
    seed_tensor = torch.tensor([seed_ids], dtype=torch.long, device=device)

    print(f"\n[Before 파인튜닝] 프롬프트: {repr(test_prompt[:30])}...")
    model.eval()
    with torch.no_grad():
        before_ids  = model.generate(seed_tensor, max_new_tokens=120, temperature=0.8, top_k=40)
    before_text = tokenizer.decode(before_ids[0].tolist())
    print(f"Before: {before_text[len(test_prompt):][:150]}")

    # ── STEP 4: 파인튜닝 학습 루프 ──────────────────────────
    print("\n[STEP 3] 파인튜닝 시작!")
    print("-" * 60)

    optimizer    = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE)
    train_losses = []
    start_time   = time.time()

    model.train()
    for epoch in range(1, MAX_EPOCHS + 1):
        epoch_loss, n_batches = 0.0, 0

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

        # GPU 메모리 출력
        if device.type == 'cuda':
            mem = torch.cuda.memory_allocated() / 1e6
            print(f"  GPU 메모리 사용: {mem:.1f} MB")

        # 10 epoch마다 샘플 확인
        if epoch % 10 == 0:
            model.eval()
            with torch.no_grad():
                sample_ids = model.generate(seed_tensor, max_new_tokens=120, temperature=0.8, top_k=40)
            sample = tokenizer.decode(sample_ids[0].tolist())
            print(f"  샘플: {sample[len(test_prompt):][:100]}")
            model.train()

    # ── STEP 5: Before / After 비교 출력 ────────────────────
    print("\n" + "=" * 60)
    print("  [Before vs After 비교]")
    print("=" * 60)
    print(f"프롬프트: {repr(test_prompt[:40])}...\n")

    model.eval()
    with torch.no_grad():
        after_ids  = model.generate(seed_tensor, max_new_tokens=150, temperature=0.8, top_k=40)
    after_text = tokenizer.decode(after_ids[0].tolist())

    print("[ Before 파인튜닝 ]")
    print(before_text[len(test_prompt):][:200])
    print()
    print("[ After 파인튜닝 ]")
    print(after_text[len(test_prompt):][:200])
    print("=" * 60)

    # ── STEP 6: 체크포인트 저장 ─────────────────────────────
    torch.save({
        'model_state' : model.state_dict(),
        'config'      : config,
        'train_losses': train_losses,
        'epoch'       : MAX_EPOCHS,
    }, FINETUNE_CKPT)
    print(f"\n체크포인트 저장됨: {FINETUNE_CKPT}")

    print("\n" + "=" * 60)
    print("  한국어 파인튜닝 완료!")
    print("\n  다음 단계: python 03_chat.py  →  '2' 선택 (한국어 모델)")
    print("=" * 60)


if __name__ == '__main__':
    main()
