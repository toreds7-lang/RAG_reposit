"""
01_pretrain_ko.py — Stage 1 (한국어): 한국어 사전 학습

[목표]
  한국어 전래동화와 민담으로 모델을 학습시킵니다.
  영어 버전(01_pretrain.py)과 구조는 동일하지만 한국어 텍스트를 사용합니다.

[영어 버전과의 차이]
  - 학습 데이터: 셰익스피어(영어) → 한국어 전래동화
  - vocab_size: ~70 → ~1,200~1,500 (한글 음절 포함)
  - GPU 감지 시 모델 크기 자동 확장 (d_model 64→128, layers 2→4)
  - DataLoader pin_memory로 GPU 전송 속도 최적화

[GPU 자동 감지]
  - GPU 있음: d_model=128, n_layers=4 → 더 좋은 품질
  - GPU 없음: d_model=64,  n_layers=2 → CPU에서 수분 내 완료

[실행]
  python 01_pretrain_ko.py

[출력]
  - checkpoints/pretrain_ko_final.pt
  - checkpoints/tokenizer_ko.json
  - loss_curve_ko.png
"""

import os
import time
import torch
from torch.utils.data import DataLoader, random_split
import matplotlib.pyplot as plt

from tokenizer import CharTokenizer
from model import ToyGPT
from data import TextDataset


# ══════════════════════════════════════════════════════════════
# 한국어 학습 텍스트 (전래동화 + 민담, 공개 도메인)
# ══════════════════════════════════════════════════════════════

KOREAN_TEXT = """
옛날 옛적에 흥부와 놀부라는 형제가 살았습니다. 형 놀부는 욕심이 많고 심술궂었지만,
동생 흥부는 마음씨가 착하고 부지런하였습니다. 놀부는 부모님이 돌아가신 후 재산을 혼자
다 차지하고 흥부를 내쫓았습니다.

흥부는 가난하게 살면서도 착한 마음을 잃지 않았습니다. 어느 봄날, 흥부는 다리가 부러진
제비를 발견하였습니다. 흥부는 정성껏 제비의 다리를 고쳐 주었습니다. 가을이 되자 제비는
따뜻한 남쪽 나라로 떠났습니다.

이듬해 봄, 제비가 돌아와 흥부에게 박씨 하나를 물어다 주었습니다. 흥부는 그 박씨를
심었습니다. 박이 무럭무럭 자라 커다란 박이 열렸습니다. 흥부가 박을 타자 안에서 금은보화가
쏟아져 나왔습니다. 흥부는 부자가 되었습니다.

이 소식을 들은 놀부는 욕심이 생겼습니다. 놀부는 일부러 제비의 다리를 부러뜨렸다가
고쳐 주었습니다. 이듬해 봄, 놀부에게도 제비가 박씨를 가져다 주었습니다. 놀부가 박을
타자 안에서 도깨비들이 나와 놀부를 혼내 주었습니다. 놀부는 잘못을 뉘우쳤고, 흥부는
형을 용서하고 함께 행복하게 살았습니다.

---

옛날에 콩쥐와 팥쥐라는 자매가 있었습니다. 친엄마를 잃은 콩쥐는 계모와 의붓언니 팥쥐와
함께 살았습니다. 계모는 콩쥐를 구박하고 힘든 일만 시켰습니다.

어느 날 마을에 잔치가 열렸습니다. 팥쥐와 계모는 예쁘게 차려입고 잔치에 갔지만,
콩쥐에게는 무거운 일감을 잔뜩 주고 다 끝내야만 갈 수 있다고 하였습니다.

콩쥐가 울고 있을 때 선녀가 나타나 일을 도와주었습니다. 선녀 덕분에 일을 모두 마친
콩쥐는 예쁜 옷을 입고 잔치에 갔습니다. 잔치에서 콩쥐는 원님의 눈에 띄었습니다.
서둘러 돌아오던 콩쥐는 꽃신 한 짝을 잃어버렸습니다.

원님은 꽃신을 들고 주인을 찾았습니다. 콩쥐의 발에 꽃신이 꼭 맞았습니다. 원님은
콩쥐를 아내로 맞이하였고, 둘은 행복하게 살았습니다.

---

옛날 옛적에 토끼와 거북이가 살았습니다. 토끼는 언제나 자신의 빠른 발을 자랑하였습니다.
거북이는 느리지만 꾸준히 자신의 길을 걸었습니다.

어느 날 토끼가 거북이에게 말하였습니다.
"거북아, 나와 달리기 시합을 하자. 넌 항상 느리잖아."
거북이는 조용히 대답하였습니다.
"좋아, 한번 해 보자."

시합이 시작되었습니다. 토끼는 빠르게 달려 나갔습니다. 한참 앞서가던 토끼는 나무 그늘
아래서 낮잠을 자기로 하였습니다.
"거북이가 저렇게 느린데, 좀 쉬어도 되겠지."

거북이는 쉬지 않고 꾸준히 걸었습니다. 결국 거북이가 먼저 결승점에 도착하였습니다.
뒤늦게 달려온 토끼는 이미 늦고 말았습니다. 토끼는 자만심 때문에 진 것을 깨달았습니다.
꾸준함이 빠름을 이긴다는 것을 모두 배웠습니다.

---

옛날에 나무꾼이 산에서 나무를 하다가 도끼를 연못에 빠뜨렸습니다. 나무꾼이 슬피 울고
있을 때 산신령이 나타났습니다.

"왜 우느냐?"
"도끼를 연못에 빠뜨렸습니다."

산신령은 금도끼를 가지고 올라왔습니다.
"이것이 네 도끼냐?"
"아닙니다, 제 도끼는 낡은 쇠도끼입니다."

산신령은 다시 은도끼를 가지고 올라왔습니다.
"이것이 네 도끼냐?"
"아닙니다, 제 도끼가 아닙니다."

마지막으로 산신령은 낡은 쇠도끼를 가지고 올라왔습니다.
"이것이 네 도끼냐?"
"예, 바로 제 도끼입니다!"

산신령은 나무꾼의 정직함을 칭찬하며 금도끼, 은도끼, 쇠도끼를 모두 주었습니다.

---

옛날에 효성이 지극한 나무꾼이 살았습니다. 어머니가 병이 들자 나무꾼은 산신령을 찾아가
도움을 구하였습니다. 산신령은 깊은 산 속 약초를 알려 주었습니다.

나무꾼은 밤낮으로 걸어 약초를 구하였습니다. 어머니는 약초를 드시고 건강을 되찾으셨습니다.
마을 사람들은 나무꾼의 효심을 칭찬하였습니다.

---

아주 먼 옛날에 하늘과 땅이 처음 만들어졌습니다. 환인의 아들 환웅은 인간 세상에 내려와
살고 싶었습니다. 환인은 아들의 뜻을 알고 태백산 신단수 아래에 내려가 세상을 다스리게
하였습니다.

환웅은 바람, 비, 구름을 다스리는 신하들과 함께 인간 세상에 내려왔습니다.
그때 곰 한 마리와 호랑이 한 마리가 환웅을 찾아와 사람이 되고 싶다고 하였습니다.
환웅은 쑥과 마늘을 주며 말하였습니다.
"이것을 먹으며 백 일 동안 햇빛을 보지 않으면 사람이 될 것이다."

호랑이는 참지 못하고 동굴 밖으로 나갔습니다. 그러나 곰은 인내하며 버텼습니다.
삼칠일이 지나 곰은 아름다운 여자로 변하였습니다. 웅녀가 된 그녀는 환웅과 혼인하여
단군을 낳았습니다. 단군은 고조선을 세웠습니다.

---

옛날에 해님과 달님이 된 오누이가 살았습니다. 어머니가 떡을 팔고 돌아오다 호랑이를
만났습니다. 호랑이는 떡을 빼앗아 먹더니 어머니마저 잡아먹었습니다.

호랑이는 어머니로 변장하여 아이들이 사는 집을 찾아갔습니다.
"얘들아, 엄마 왔다. 문 열어 다오."
오누이는 이상한 낌새를 느끼고 문을 열어 주지 않았습니다.

호랑이가 안으로 들어오자 오누이는 뒷문으로 달아나 나무 위로 올라갔습니다. 호랑이도
나무 위로 올라오려 하자 오누이는 하늘에 빌었습니다.
"하늘이시여, 저희를 살려 주시려면 새 동아줄을 내려 주시고, 죽이시려면 썩은 동아줄을
내려 주소서."

하늘에서 새 동아줄이 내려왔습니다. 오누이는 줄을 잡고 하늘로 올라갔습니다.
오빠는 해님이 되고 누이는 달님이 되었습니다.

---

한국에는 아름다운 자연이 있습니다. 봄에는 진달래와 벚꽃이 피고, 여름에는 초록 산과
맑은 강이 있습니다. 가을에는 단풍이 물들고, 겨울에는 하얀 눈이 내립니다.

한국 사람들은 예로부터 자연을 사랑하고 함께 살아왔습니다. 산과 강, 바다가 어우러진
아름다운 나라입니다.

한국의 음식으로는 김치, 불고기, 비빔밥, 된장찌개, 삼겹살 등이 있습니다. 김치는 배추나
무를 소금에 절여 양념하여 발효시킨 음식입니다. 비빔밥은 밥 위에 여러 가지 나물과
고기, 달걀을 올려 고추장과 함께 비벼 먹는 음식입니다.

한국의 전통 명절로는 설날과 추석이 있습니다. 설날에는 가족이 모여 차례를 지내고
세배를 합니다. 추석에는 강강술래를 하고 송편을 만들어 먹습니다.

한국의 전통 의상은 한복입니다. 한복은 색깔이 아름답고 형태가 우아합니다.
한국의 전통 음악은 국악이라 하며, 가야금, 거문고, 해금 등의 악기를 사용합니다.

---

세종대왕은 조선의 네 번째 왕으로 1397년에 태어났습니다. 세종대왕은 백성을 사랑하는
마음이 깊었습니다. 당시 우리말을 표현할 고유한 글자가 없어 백성들이 어려움을 겪었습니다.

세종대왕은 집현전 학자들과 함께 훈민정음을 만들었습니다. 훈민정음은 1443년에 완성되었습니다.
훈민정음은 오늘날 한글로 불리며 우리 민족의 자랑스러운 문화유산입니다.

한글은 소리를 기호로 나타낸 과학적인 문자입니다. 자음 14개와 모음 10개로 이루어져 있으며,
이를 결합하여 수천 가지 음절을 표현할 수 있습니다. 한글은 배우기 쉽고 쓰기 편리하여
세계에서 가장 우수한 문자 중 하나로 인정받고 있습니다.

---

이순신 장군은 조선 시대의 위대한 장군입니다. 이순신 장군은 1545년에 태어났습니다.
임진왜란 때 이순신 장군은 거북선을 이용하여 왜군을 물리쳤습니다. 거북선은 세계 최초의
철갑선으로 알려져 있습니다.

이순신 장군은 명량 해전, 한산도 대첩 등 수많은 전투에서 승리하였습니다.
나라를 구한 이순신 장군은 오늘날에도 많은 사람들에게 존경받고 있습니다.

---

옛날에 심청이라는 효녀가 살았습니다. 심청의 아버지 심봉사는 눈이 먼 장님이었습니다.
심청은 아버지의 눈을 뜨게 하기 위해 공양미 삼백 석에 자신의 몸을 팔았습니다.

심청은 배를 타고 인당수에 몸을 던졌습니다. 옥황상제는 심청의 효심에 감동하여 심청을
연꽃 속에 태워 세상으로 돌려보냈습니다.

왕이 연꽃을 발견하여 궁으로 가져오자 연꽃이 피면서 심청이 나왔습니다. 왕은 심청을
왕비로 맞이하였습니다. 심청은 잔치를 열어 온 나라의 장님들을 초대하였습니다.
아버지 심봉사도 잔치에 와서 딸 심청을 만나는 순간 눈을 떴습니다.

---

옛날에 한 마을에 원님이 새로 부임하였습니다. 원님은 마을 사람들의 다툼을 공정하게
해결하기로 하였습니다.

어느 날 두 사람이 원님 앞에 왔습니다. 한 사람은 부자이고 다른 한 사람은 가난한
떡 장수였습니다. 부자는 떡 장수가 자신의 돈을 훔쳤다고 주장하였습니다.

원님은 곰곰이 생각한 후 말하였습니다.
"떡 굽는 냄새를 맡은 것의 값을 돈 소리로 치르면 된다."

원님은 부자에게 동전을 서로 부딪쳐 소리를 내게 하고, 그 소리를 들은 것으로 값을 갚게
하였습니다. 모두가 원님의 슬기로운 판결에 감탄하였습니다.

---

봄이 되면 들에는 꽃들이 피어납니다. 진달래, 개나리, 벚꽃이 차례로 피어 아름다운 봄
풍경을 만들어 냅니다. 아이들은 들판에서 뛰어 놀고, 어른들은 꽃놀이를 즐깁니다.

여름에는 초록빛 나뭇잎이 무성하게 자랍니다. 더운 여름날 시원한 냇가에서 물놀이를 즐기고,
맛있는 수박을 먹습니다. 밤하늘에는 반딧불이가 반짝입니다.

가을에는 나뭇잎이 빨갛고 노랗게 물듭니다. 들판에는 황금빛 벼가 익어갑니다. 사람들은
단풍 구경을 나가고, 추석에는 가족들이 모여 차례를 지냅니다.

겨울에는 하얀 눈이 내립니다. 아이들은 눈사람을 만들고 썰매를 탑니다. 따뜻한 방에서
가족들이 모여 이야기를 나눕니다.

---

옛날에 어느 마을에 게으른 농부가 살았습니다. 그는 항상 일하기 싫어하고 쉬기만 하였습니다.
어느 날 하늘에서 선녀가 내려와 말하였습니다.
"부지런히 일하는 자에게 복이 온다."

농부는 그 말을 듣고 마음을 바꾸었습니다. 다음 날부터 농부는 새벽부터 일어나 열심히
밭을 일구었습니다. 씨를 뿌리고 물을 주고 잡초를 뽑았습니다.

가을이 되자 농부의 밭에는 풍성한 열매가 맺혔습니다. 마을 사람들도 농부의 변화를
보고 함께 기뻐하였습니다. 부지런함이 복을 가져다 준다는 것을 모두 알게 되었습니다.

---

산 속에 지혜로운 토끼가 살았습니다. 어느 날 사자가 토끼에게 자신의 먹이가 되라고
하였습니다. 토끼는 재치를 발휘하였습니다.

"사자님, 저보다 더 크고 맛있는 먹이가 있습니다. 저를 따라오세요."

토끼는 사자를 우물가로 데려갔습니다.
"우물 안을 보세요. 더 큰 사자가 있지 않습니까?"

사자는 자신의 모습이 비친 것을 보고 우물 안의 사자에게 달려들었습니다. 사자는 우물에
빠지고 말았습니다. 토끼는 위기에서 벗어났습니다. 지혜는 힘보다 강합니다.

---

한국의 속담에는 깊은 지혜가 담겨 있습니다.

가는 말이 고와야 오는 말이 곱다는 것은 남에게 좋게 대해야 나도 좋은 대우를 받는다는
뜻입니다.

백지장도 맞들면 낫다는 것은 어떤 일이든 혼자 하는 것보다 여럿이 함께 하면 더 쉽다는
뜻입니다.

세 살 버릇 여든까지 간다는 말은 어릴 때 몸에 밴 버릇은 나이가 들어도 잘 고쳐지지
않으니 어릴 때부터 좋은 습관을 길러야 한다는 뜻입니다.

티끌 모아 태산이라는 것은 작은 것이라도 모이면 큰 것이 된다는 뜻입니다.

하늘은 스스로 돕는 자를 돕는다는 것은 자신이 노력해야 다른 도움도 의미가 있다는 뜻입니다.

---

"""

# 텍스트를 반복하여 학습량 확보
KOREAN_TEXT = KOREAN_TEXT * 8


# ══════════════════════════════════════════════════════════════
# GPU 감지 및 하이퍼파라미터 자동 설정
# ══════════════════════════════════════════════════════════════

def get_device_and_config():
    """GPU 유무에 따라 디바이스와 모델 크기를 결정합니다."""
    if torch.cuda.is_available():
        device = torch.device("cuda")
        gpu_name = torch.cuda.get_device_name(0)
        gpu_mem  = torch.cuda.get_device_properties(0).total_memory / 1e9
        print(f"GPU 감지: {gpu_name}")
        print(f"GPU 메모리: {gpu_mem:.1f} GB")
        # GPU는 더 큰 모델 사용 → 더 좋은 품질
        model_cfg = dict(d_model=128, n_layers=4, n_heads=8, d_ff=512)
        batch_size = 128
    else:
        device = torch.device("cpu")
        print("CPU 모드 (GPU 없음)")
        # CPU는 작은 모델 → 수분 내 완료
        model_cfg = dict(d_model=64, n_layers=2, n_heads=4, d_ff=256)
        batch_size = 64
    return device, model_cfg, batch_size


# ══════════════════════════════════════════════════════════════
# 고정 하이퍼파라미터 (모델 크기와 무관)
# ══════════════════════════════════════════════════════════════

CONTEXT_LEN   = 128
LEARNING_RATE = 3e-4
MAX_EPOCHS    = 5
VAL_RATIO     = 0.1
DROPOUT       = 0.1

CHECKPOINT_DIR  = "checkpoints"
CHECKPOINT_PATH = os.path.join(CHECKPOINT_DIR, "pretrain_ko_final.pt")
TOKENIZER_PATH  = os.path.join(CHECKPOINT_DIR, "tokenizer_ko.json")
LOSS_CURVE_PATH = "loss_curve_ko.png"

torch.manual_seed(42)


# ══════════════════════════════════════════════════════════════
# 유틸리티 함수
# ══════════════════════════════════════════════════════════════

def evaluate(model, loader, device):
    model.eval()
    total_loss, count = 0.0, 0
    with torch.no_grad():
        for x, y in loader:
            x, y = x.to(device), y.to(device)
            _, loss = model(x, targets=y)
            total_loss += loss.item()
            count += 1
    model.train()
    return total_loss / count if count > 0 else float('inf')


def generate_sample(model, tokenizer, device, seed_text="옛날에", max_tokens=150):
    model.eval()
    ids = tokenizer.encode(seed_text)
    if not ids:
        return "(샘플 생성 실패)"
    idx = torch.tensor([ids], dtype=torch.long, device=device)
    output = model.generate(idx, max_new_tokens=max_tokens, temperature=0.8, top_k=40)
    model.train()
    return tokenizer.decode(output[0].tolist())


# ══════════════════════════════════════════════════════════════
# 메인 학습 루프
# ══════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("  Stage 1 (한국어): 사전 학습 (Pre-training)")
    print("=" * 60)

    # ── 디바이스 및 모델 크기 결정 ───────────────────────────
    device, model_cfg, batch_size = get_device_and_config()
    print(f"\n모델 설정: {model_cfg}")
    print(f"배치 크기: {batch_size}")

    # ── STEP 1: 데이터 준비 ──────────────────────────────────
    print("\n[STEP 1] 데이터 준비 중...")
    text = KOREAN_TEXT
    print(f"텍스트 크기: {len(text):,} 문자")

    tokenizer = CharTokenizer(text)
    os.makedirs(CHECKPOINT_DIR, exist_ok=True)
    tokenizer.save(TOKENIZER_PATH)
    print(f"어휘 크기 (vocab_size): {tokenizer.vocab_size}")

    token_ids = tokenizer.encode(text)
    print(f"총 토큰 수: {len(token_ids):,}")

    full_dataset = TextDataset(token_ids, CONTEXT_LEN)
    val_size   = int(len(full_dataset) * VAL_RATIO)
    train_size = len(full_dataset) - val_size
    from torch.utils.data import random_split
    train_ds, val_ds = random_split(full_dataset, [train_size, val_size])

    # pin_memory: GPU 전송 속도 향상 (CPU→GPU 복사를 비동기로 처리)
    use_pin = device.type == 'cuda'
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True,
                              pin_memory=use_pin)
    val_loader   = DataLoader(val_ds,   batch_size=batch_size, shuffle=False,
                              pin_memory=use_pin)

    print(f"학습 샘플: {train_size:,}  |  검증 샘플: {val_size:,}")

    # ── STEP 2: 모델 초기화 ──────────────────────────────────
    print("\n[STEP 2] 모델 초기화 중...")
    model = ToyGPT(
        vocab_size  = tokenizer.vocab_size,
        context_len = CONTEXT_LEN,
        dropout     = DROPOUT,
        **model_cfg,
    ).to(device)

    print(f"총 파라미터 수: {model.count_parameters():,}")

    optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE)

    # ── STEP 3: 학습 루프 ────────────────────────────────────
    print("\n[STEP 3] 학습 시작!")
    print("-" * 60)

    train_losses, val_losses = [], []
    start_time = time.time()

    for epoch in range(1, MAX_EPOCHS + 1):
        epoch_loss, n_batches = 0.0, 0

        for i, (x, y) in enumerate(train_loader):
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
                f"Batch {i+1}/{len(train_loader)} | "
                f"Loss: {loss.item():.4f}",
                end='', flush=True
            )

        avg_train = epoch_loss / n_batches
        avg_val   = evaluate(model, val_loader, device)
        elapsed   = time.time() - start_time

        train_losses.append(avg_train)
        val_losses.append(avg_val)

        print(f"\nEpoch {epoch}/{MAX_EPOCHS} 완료 | "
              f"학습 손실: {avg_train:.4f} | "
              f"검증 손실: {avg_val:.4f} | "
              f"경과: {elapsed:.1f}s")

        # GPU 메모리 사용량 출력
        if device.type == 'cuda':
            mem = torch.cuda.memory_allocated() / 1e6
            print(f"  GPU 메모리 사용: {mem:.1f} MB")

        sample = generate_sample(model, tokenizer, device)
        print(f"\n--- 생성 샘플 (Epoch {epoch}) ---")
        print(sample[:300])
        print("-" * 60)

    total_time = time.time() - start_time
    print(f"\n총 학습 시간: {total_time:.1f}초 ({total_time/60:.1f}분)")

    # ── STEP 4: 손실 그래프 ──────────────────────────────────
    plt.figure(figsize=(10, 4))
    plt.plot(range(1, MAX_EPOCHS + 1), train_losses, 'b-o', label='학습 손실')
    plt.plot(range(1, MAX_EPOCHS + 1), val_losses,   'r-o', label='검증 손실')
    plt.xlabel('Epoch')
    plt.ylabel('Loss')
    plt.title('한국어 사전 학습 손실 곡선')
    plt.legend()
    plt.tight_layout()
    plt.savefig(LOSS_CURVE_PATH, dpi=120)
    try:
        plt.show()
    except Exception:
        pass
    plt.close()
    print(f"손실 그래프 저장됨: {LOSS_CURVE_PATH}")

    # ── STEP 5: 체크포인트 저장 ─────────────────────────────
    torch.save({
        'model_state' : model.state_dict(),
        'config'      : {
            'vocab_size' : tokenizer.vocab_size,
            'context_len': CONTEXT_LEN,
            'dropout'    : DROPOUT,
            **model_cfg,
        },
        'train_losses': train_losses,
        'val_losses'  : val_losses,
        'epoch'       : MAX_EPOCHS,
    }, CHECKPOINT_PATH)
    print(f"체크포인트 저장됨: {CHECKPOINT_PATH}")

    print("\n" + "=" * 60)
    print("  한국어 사전 학습 완료!")
    print(f"  최종 학습 손실: {train_losses[-1]:.4f}")
    print("\n  다음 단계: python 02_finetune_ko.py")
    print("=" * 60)


if __name__ == '__main__':
    main()
