"""
tokenizer.py — 문자 단위 토크나이저 (Character-level Tokenizer)

핵심 개념:
  - 텍스트의 모든 고유 문자를 정수로 매핑합니다.
  - 예: 'A' → 0, 'B' → 1, ... (학습 코퍼스 기준)
  - vocab_size가 매우 작아(~70) 모델 구조를 직관적으로 이해할 수 있습니다.
"""

import json


class CharTokenizer:
    """
    문자 단위 토크나이저.

    사용 예시:
        tokenizer = CharTokenizer("hello world")
        ids = tokenizer.encode("hello")   # [7, 4, 11, 11, 14]
        text = tokenizer.decode(ids)      # "hello"
    """

    def __init__(self, text: str):
        """
        텍스트 코퍼스에서 어휘(vocab)를 자동으로 구축합니다.

        Args:
            text: 어휘를 추출할 원본 텍스트
        """
        # 고유 문자를 정렬하여 재현 가능한 vocab 생성
        chars = sorted(set(text))
        self.vocab = {ch: i for i, ch in enumerate(chars)}       # char → id
        self.inv_vocab = {i: ch for ch, i in self.vocab.items()} # id → char

    @property
    def vocab_size(self) -> int:
        """어휘 크기 (고유 문자 수)"""
        return len(self.vocab)

    def encode(self, text: str) -> list:
        """
        문자열을 정수 리스트로 변환합니다.

        Args:
            text: 인코딩할 문자열
        Returns:
            정수 ID 리스트
        """
        return [self.vocab[ch] for ch in text if ch in self.vocab]

    def decode(self, ids: list) -> str:
        """
        정수 리스트를 문자열로 변환합니다.

        Args:
            ids: 정수 ID 리스트
        Returns:
            복원된 문자열
        """
        return ''.join(self.inv_vocab.get(i, '') for i in ids)

    def save(self, path: str):
        """
        토크나이저를 JSON 파일로 저장합니다.
        모델 체크포인트와 함께 보관하여 추후 로드 시 사용합니다.
        """
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.vocab, f, ensure_ascii=False, indent=2)
        print(f"토크나이저 저장됨: {path}  (vocab_size={self.vocab_size})")

    @classmethod
    def load(cls, path: str) -> 'CharTokenizer':
        """
        저장된 JSON 파일에서 토크나이저를 복원합니다.

        Args:
            path: tokenizer.save()로 저장한 JSON 경로
        Returns:
            복원된 CharTokenizer 인스턴스
        """
        # 빈 인스턴스를 만들고 vocab을 직접 주입합니다.
        tokenizer = cls.__new__(cls)
        with open(path, 'r', encoding='utf-8') as f:
            tokenizer.vocab = json.load(f)
        tokenizer.inv_vocab = {v: k for k, v in tokenizer.vocab.items()}
        return tokenizer


# ──────────────────────────────────────────────
# 실행 시 간단한 동작 확인
# ──────────────────────────────────────────────
if __name__ == '__main__':
    sample_text = "Hello, World! 안녕하세요."
    tok = CharTokenizer(sample_text)

    print(f"vocab_size : {tok.vocab_size}")
    print(f"vocab      : {tok.vocab}")

    ids = tok.encode("Hello")
    print(f"encode('Hello') → {ids}")
    print(f"decode({ids})   → '{tok.decode(ids)}'")
