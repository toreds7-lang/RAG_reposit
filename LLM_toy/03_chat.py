"""
03_chat.py — Stage 3: 대화 (Chat)

[목표]
  파인튜닝된 모델과 대화합니다.
  토큰이 하나씩 생성되어 출력되는 것을 실시간으로 확인할 수 있습니다.
  이것이 ChatGPT, Claude 등이 동작하는 실제 방식입니다.

[핵심 개념]
  - 자기회귀 생성(Autoregressive Generation): 매번 1개의 토큰만 생성
  - 스트리밍 출력: print(char, end='', flush=True) — 실시간 표시
  - Temperature: 높을수록 창의적, 낮을수록 일관적

[실행]
  python 03_chat.py
  → 실행 후 [1] 영어 모델  [2] 한국어 모델 선택

[명령어]
  /quit  또는  /exit  — 종료
  /temp [값]          — temperature 변경 (예: /temp 0.5)
  /reset              — 대화 초기화
  /pretrain           — 사전 학습 모델로 전환 (비교용)
  /finetune           — 파인튜닝 모델로 전환
"""

import os
import time
import torch

from tokenizer import CharTokenizer
from model import ToyGPT


# ══════════════════════════════════════════════════════════════
# 영어 / 한국어 모델 체크포인트 경로
# ══════════════════════════════════════════════════════════════

CONFIGS = {
    "en": {
        "pretrain" : "checkpoints/pretrain_final.pt",
        "finetune" : "checkpoints/finetune_final.pt",
        "tokenizer": "checkpoints/tokenizer.json",
        "label"    : "영어 (Shakespeare)",
    },
    "ko": {
        "pretrain" : "checkpoints/pretrain_ko_final.pt",
        "finetune" : "checkpoints/finetune_ko_final.pt",
        "tokenizer": "checkpoints/tokenizer_ko.json",
        "label"    : "한국어",
    },
}

DEFAULT_TEMPERATURE = 0.8
DEFAULT_TOP_K       = 40
MAX_NEW_TOKENS      = 200

STOP_SEQUENCE = "\nQ:"


# ══════════════════════════════════════════════════════════════
# 모델 로드 헬퍼
# ══════════════════════════════════════════════════════════════

def load_model(ckpt_path: str, device: torch.device):
    """체크포인트에서 모델을 로드합니다."""
    assert os.path.exists(ckpt_path), (
        f"\n오류: '{ckpt_path}'를 찾을 수 없습니다.\n"
        "해당 언어의 pretrain → finetune 스크립트를 먼저 실행하세요."
    )
    ckpt  = torch.load(ckpt_path, map_location=device, weights_only=True)
    model = ToyGPT(**ckpt['config']).to(device)
    model.load_state_dict(ckpt['model_state'])
    model.eval()
    return model, ckpt['config']


# ══════════════════════════════════════════════════════════════
# 스트리밍 토큰 생성 (핵심 강의 포인트!)
# ══════════════════════════════════════════════════════════════

def stream_generate(
    model: ToyGPT,
    tokenizer: CharTokenizer,
    prompt: str,
    device: torch.device,
    temperature: float = 0.8,
    top_k: int = 40,
    max_new_tokens: int = 200,
) -> int:
    """
    토큰을 하나씩 생성하면서 실시간으로 출력합니다.

    [핵심 개념]
    이 함수 안의 for 루프가 GPT의 실제 동작 방식입니다:
      - 매 반복마다 forward pass 1회
      - 마지막 위치의 logits에서 다음 토큰 샘플링
      - 새 토큰을 컨텍스트에 추가하고 반복

    이것이 왜 느린지 이해할 수 있습니다:
      100 토큰 생성 = forward pass 100회!

    Returns:
        생성된 토큰 수
    """
    model.eval()
    with torch.no_grad():
        ids = tokenizer.encode(prompt)
        if not ids:
            print("(인코딩 실패: 알 수 없는 문자)")
            return 0

        context        = torch.tensor([ids], dtype=torch.long, device=device)
        generated_text = ""
        n_tokens       = 0

        for _ in range(max_new_tokens):
            # context_len 초과 시 오른쪽 잘라냄
            context_crop = context[:, -model.context_len:]

            # ── 핵심: 매번 1회의 forward pass ──────────────────
            logits, _   = model(context_crop)
            next_logits = logits[0, -1, :]      # 마지막 위치 logits

            # Temperature 스케일링
            next_logits = next_logits / temperature

            # Top-k 필터링
            top_vals, _ = torch.topk(next_logits, min(top_k, next_logits.size(-1)))
            threshold   = top_vals[-1]
            next_logits = next_logits.masked_fill(next_logits < threshold, float('-inf'))

            # 확률 분포에서 샘플링
            probs      = torch.softmax(next_logits, dim=-1)
            next_token = torch.multinomial(probs, num_samples=1).unsqueeze(0)  # (1,1)

            # ── 실시간 스트리밍 출력 ────────────────────────────
            char = tokenizer.decode([next_token.item()])
            print(char, end='', flush=True)
            generated_text += char
            n_tokens += 1

            # 컨텍스트에 새 토큰 추가
            context = torch.cat([context, next_token], dim=1)

            # 종료 조건: 다음 Q가 시작되면 멈춤
            if generated_text.endswith(STOP_SEQUENCE):
                break

    return n_tokens


# ══════════════════════════════════════════════════════════════
# 메인 대화 루프
# ══════════════════════════════════════════════════════════════

def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if device.type == 'cuda':
        print(f"GPU: {torch.cuda.get_device_name(0)}")

    # ── 언어 선택 ────────────────────────────────────────────
    print("\n사용할 모델을 선택하세요:")
    print("  [1] 영어 모델 (Shakespeare 사전 학습)")
    print("  [2] 한국어 모델 (전래동화 사전 학습)")

    while True:
        choice = input("선택 (1 또는 2, 기본값 1): ").strip() or "1"
        if choice in ("1", "2"):
            break
        print("1 또는 2를 입력하세요.")

    lang = "en" if choice == "1" else "ko"
    cfg  = CONFIGS[lang]
    print(f"[{cfg['label']} 모델 선택됨]")

    # ── 체크포인트 존재 확인 ─────────────────────────────────
    for key in ("pretrain", "finetune", "tokenizer"):
        if not os.path.exists(cfg[key]):
            script = "01_pretrain" + ("_ko" if lang == "ko" else "")
            print(f"\n오류: '{cfg[key]}'를 찾을 수 없습니다.")
            print(f"먼저 {script}.py → 02_finetune{'_ko' if lang == 'ko' else ''}.py 를 실행하세요.")
            return

    # ── 모델 로드 ────────────────────────────────────────────
    tokenizer = CharTokenizer.load(cfg['tokenizer'])

    print("파인튜닝 모델 로드 중...", end=' ', flush=True)
    finetune_model, config = load_model(cfg['finetune'], device)
    print("완료")

    print("사전 학습 모델 로드 중...", end=' ', flush=True)
    pretrain_model, _ = load_model(cfg['pretrain'], device)
    print("완료")

    current_model      = finetune_model
    current_model_name = f"파인튜닝 모델 ({cfg['label']})"

    # ── 배너 출력 ────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  ToyGPT 대화 시스템")
    print("=" * 60)
    print(f"  언어        : {cfg['label']}")
    print(f"  모델 파라미터: {current_model.count_parameters():,}")
    print(f"  어휘 크기    : {tokenizer.vocab_size}")
    print(f"  디바이스     : {device}")
    print()
    print("  명령어:")
    print("    /quit              — 종료")
    print("    /temp [숫자]        — temperature 변경 (예: /temp 0.5)")
    print("    /reset             — 대화 초기화")
    print("    /pretrain          — 사전 학습 모델로 전환 (비교용)")
    print("    /finetune          — 파인튜닝 모델로 전환")
    print("=" * 60)

    temperature = DEFAULT_TEMPERATURE

    try:
        user_temp = input(f"\nTemperature [기본값 {DEFAULT_TEMPERATURE}, Enter로 기본값 사용]: ").strip()
        if user_temp:
            temperature = float(user_temp)
    except (ValueError, EOFError):
        pass
    print(f"Temperature: {temperature}")

    # ── 대화 루프 ────────────────────────────────────────────
    print("\n대화를 시작합니다. (질문을 입력하세요)\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input:
            continue

        # ── 명령어 처리 ──────────────────────────────────────
        if user_input.lower() in ('/quit', '/exit', '/종료'):
            break

        if user_input.lower() == '/pretrain':
            current_model      = pretrain_model
            current_model_name = f"사전 학습 모델 ({cfg['label']})"
            print(f"[{current_model_name}으로 전환됨]")
            continue

        if user_input.lower() == '/finetune':
            current_model      = finetune_model
            current_model_name = f"파인튜닝 모델 ({cfg['label']})"
            print(f"[{current_model_name}으로 전환됨]")
            continue

        if user_input.lower() == '/reset':
            print("[대화가 초기화되었습니다]")
            continue

        if user_input.lower().startswith('/temp '):
            try:
                temperature = float(user_input.split()[1])
                print(f"[Temperature → {temperature}]")
            except (IndexError, ValueError):
                print("사용법: /temp [숫자]  예: /temp 0.5")
            continue

        # ── 응답 생성 ─────────────────────────────────────────
        prompt = f"\nQ: {user_input}\nA:"

        print(f"\nAI ({current_model_name}): ", end='', flush=True)
        t_start = time.time()

        n_tokens = stream_generate(
            model          = current_model,
            tokenizer      = tokenizer,
            prompt         = prompt,
            device         = device,
            temperature    = temperature,
            top_k          = DEFAULT_TOP_K,
            max_new_tokens = MAX_NEW_TOKENS,
        )

        elapsed     = time.time() - t_start
        tok_per_sec = n_tokens / elapsed if elapsed > 0 else 0
        print(f"\n[{n_tokens} 토큰, {tok_per_sec:.1f} tok/s]\n")

    print("\n대화를 종료합니다. 감사합니다!")


if __name__ == '__main__':
    main()
