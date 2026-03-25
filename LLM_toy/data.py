"""
data.py — 데이터셋 헬퍼

[핵심 개념] 언어 모델 학습 데이터:
  - 입력(x): 토큰 [t0, t1, t2, ..., t_{T-1}]
  - 정답(y): 토큰 [t1, t2, t3, ..., t_T]     ← x를 한 칸 오른쪽 shift
  - 즉, "이전 토큰들이 주어졌을 때 다음 토큰 예측"이 목표입니다.
"""

import os
import urllib.request
import torch
from torch.utils.data import Dataset


# ══════════════════════════════════════════════════════════════
# 1. Tiny Shakespeare 데이터 로드
# ══════════════════════════════════════════════════════════════

# Andrej Karpathy의 char-rnn에서 사용한 셰익스피어 데이터
_SHAKESPEARE_URL = (
    "https://raw.githubusercontent.com/karpathy/char-rnn/"
    "master/data/tinyshakespeare/input.txt"
)

# 다운로드 실패 시 사용할 백업 텍스트 (셰익스피어 소네트 일부)
_FALLBACK_TEXT = """
First Citizen:
Before we proceed any further, hear me speak.

All:
Speak, speak.

First Citizen:
You are all resolved rather to die than to famish?

All:
Resolved. resolved.

First Citizen:
First, you know Caius Marcius is chief enemy to the people.

All:
We know't, we know't.

First Citizen:
Let us kill him, and we'll have corn at our own price.
Is't a verdict?

All:
No more talking on't; let it be done: away, away!

Second Citizen:
One word, good citizens.

First Citizen:
We are accounted poor citizens, the patricians good.
What authority surfeits on would relieve us: if they
would yield us but the superfluity, while it were
wholesome, we might guess they relieved us humanely;
but they think we are too dear: the leanness that
afflicts us, the object of our misery, is as an
inventory to particularise their abundance; our
sufferance is a gain to them Let us revenge this with
our pikes, ere we become rakes: for the gods know I
speak this in hunger for bread, not in thirst for revenge.

Second Citizen:
Would you proceed especially against Caius Marcius?

All:
Against him first: he's a very dog to the commonalty.

Second Citizen:
Consider you what services he has done for his country?

First Citizen:
Very well; and could be content to give him good
report fort, but that he pays himself with being proud.

Second Citizen:
Nay, but speak not maliciously.

First Citizen:
I say unto you, what he hath done famously, he did
it to that end: though soft-conscienced men can be
content to say it was for his country he did it to
please his mother and to be partly proud; which he
is, even till the altitude of his virtue.

Second Citizen:
What he cannot help in his nature, you account a
vice in him. You must in no way say he is covetous.

First Citizen:
If I must not, I need not be barren of accusations;
he hath faults, with surplus, to tire in repetition.
What shouts are these? The other side o' the city
is risen: why stay we prating here? to the Capitol!

All:
Come, come.

First Citizen:
Soft! who comes here?

Second Citizen:
Worthy Menenius Agrippa; one that hath always loved
the people.

First Citizen:
He's one honest enough: would all the rest were so!

Menenius:
What work's, my countrymen, in hand? where go you
With bats and clubs? The matter? speak, I pray you.

First Citizen:
Our business is not unknown to the senate; they have
had inkling this fortnight what we intend to do,
which now we'll show 'em in deeds. They say poor
suitors have strong breaths: they shall know we
have strong arms too.
""" * 20  # 반복하여 충분한 학습 데이터 확보


def get_shakespeare(cache_path: str = "shakespeare.txt") -> str:
    """
    Tiny Shakespeare 텍스트를 반환합니다.

    - 캐시 파일이 있으면 파일에서 로드합니다.
    - 없으면 인터넷에서 다운로드합니다.
    - 다운로드 실패 시 내장 백업 텍스트를 사용합니다.

    Args:
        cache_path: 캐시 파일 경로 (기본: 'shakespeare.txt')
    Returns:
        셰익스피어 텍스트 문자열
    """
    if os.path.exists(cache_path):
        print(f"캐시에서 로드: {cache_path}")
        with open(cache_path, 'r', encoding='utf-8') as f:
            return f.read()

    print(f"다운로드 중: {_SHAKESPEARE_URL}")
    try:
        urllib.request.urlretrieve(_SHAKESPEARE_URL, cache_path)
        print(f"다운로드 완료: {cache_path}")
        with open(cache_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"다운로드 실패: {e}")
        print("내장 백업 텍스트를 사용합니다.")
        # 백업 텍스트를 캐시로 저장
        with open(cache_path, 'w', encoding='utf-8') as f:
            f.write(_FALLBACK_TEXT)
        return _FALLBACK_TEXT


# ══════════════════════════════════════════════════════════════
# 2. TextDataset — PyTorch 데이터셋
# ══════════════════════════════════════════════════════════════

class TextDataset(Dataset):
    """
    슬라이딩 윈도우 방식의 텍스트 데이터셋.

    예시 (context_len=4):
        토큰 시퀀스: [10, 20, 30, 40, 50, 60]
        인덱스 0:  x=[10,20,30,40], y=[20,30,40,50]
        인덱스 1:  x=[20,30,40,50], y=[30,40,50,60]
        ...

    Args:
        token_ids  : 정수 토큰 ID 리스트
        context_len: 하나의 샘플에서 사용할 시퀀스 길이
    """

    def __init__(self, token_ids: list, context_len: int):
        self.data = torch.tensor(token_ids, dtype=torch.long)
        self.context_len = context_len

    def __len__(self) -> int:
        # 마지막 context_len 개 위치는 y를 만들 수 없으므로 제외
        return len(self.data) - self.context_len

    def __getitem__(self, idx: int):
        x = self.data[idx : idx + self.context_len]
        y = self.data[idx + 1 : idx + self.context_len + 1]
        return x, y


# ──────────────────────────────────────────────
# 실행 시 동작 확인
# ──────────────────────────────────────────────
if __name__ == '__main__':
    text = get_shakespeare()
    print(f"텍스트 길이: {len(text):,} 문자")
    print(f"처음 100자:\n{text[:100]}")

    # 간단한 데이터셋 테스트
    from tokenizer import CharTokenizer
    tok = CharTokenizer(text)
    ids = tok.encode(text[:1000])
    ds = TextDataset(ids, context_len=32)
    x, y = ds[0]
    print(f"\n데이터셋 크기: {len(ds)}")
    print(f"x[:10]: {x[:10].tolist()}")
    print(f"y[:10]: {y[:10].tolist()}")
    print(f"→ x[0]='{tok.decode([x[0].item()])}', y[0]='{tok.decode([y[0].item()])}'")
