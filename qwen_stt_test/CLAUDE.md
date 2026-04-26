# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Single-file Streamlit push-to-talk voice chat for Windows/CPU. Flow:
`mic (streamlit-mic-recorder) -> wav_bytes_to_mono16k() -> Whisper tiny (local) -> OpenAI chat (gpt-4o-mini) -> text`.
TTS output is intentionally deferred — see [TTS_FUTURE.md](TTS_FUTURE.md).

## Common commands (Windows, Git Bash shown; PowerShell equivalents in SETUP.md)

- Activate venv: `source .venv/Scripts/activate`
- Install deps: `pip install -r requirements.txt`
- Run app: `streamlit run app.py` (serves on http://localhost:8501)
- Syntax check: `python -m py_compile app.py`

There is no linter, formatter, or test suite configured. Do not add one unless asked.

## Non-obvious design constraints — do not "fix" these back

- **Python 3.11 only.** `numba`/`llvmlite` CPU wheels pulled in by `openai-whisper` are unreliable on 3.12+ in this environment. The `.venv` is 3.11; keep it.
- **No ffmpeg.** Whisper's default path calls `ffmpeg` via subprocess and was failing on the user's machine. [app.py:36](app.py#L36) `wav_bytes_to_mono16k()` decodes the recorder's WAV blob with stdlib `wave` + numpy (mono downmix, linear-interp resample to 16 kHz) and passes a float32 array directly to `model.transcribe()`. Do not reintroduce `ffmpeg` as a dep, and do not pass file paths to `transcribe()`.
- **Whisper weights are committed at [models/tiny.pt](models/tiny.pt) (~73 MB).** Loaded via `whisper.load_model("tiny", download_root=WHISPER_MODEL_DIR)` at [app.py:21](app.py#L21). This is deliberate: the user's work network blocks both HF and the OpenAI model CDN. Do not remove the file or switch back to the default cache.
- **HuggingFace is a hard "no" at install time.** Do not add deps that download from HF on first run (e.g. `faster-whisper`, `transformers`-backed pipelines). Work network blocks HF; home network is used only for occasional one-off downloads documented in TTS_FUTURE.md.
- **`mic_recorder` uses a dynamic key + `just_once=True`** at [app.py:97-104](app.py#L97-L104): `key=f"mic_{st.session_state.mic_turn}"`, and `mic_turn` is bumped + `st.rerun()` after each processed turn. This is the fix for a stuck-widget bug where the 3rd+ recording wasn't registering. Do not change back to a static key or `just_once=False`.
- **Chat history lives in `st.session_state.messages` including the system prompt at index 0.** The render loop skips role `"system"` but the OpenAI call sends the whole list. "Clear chat" resets to just the system message and bumps `mic_turn`.

## File map

- [app.py](app.py) — the entire app (~130 lines). Cached resource loaders at top, `wav_bytes_to_mono16k` decoder, `main()` with sidebar + chat render + mic handling.
- [requirements.txt](requirements.txt) — intentionally minimal. `torch` is pulled in transitively by `openai-whisper`.
- [models/tiny.pt](models/tiny.pt) — bundled Whisper weights. Git-tracked.
- [SETUP.md](SETUP.md) — Korean install guide for the user's work PC (clone → venv → `.env` → run).
- [TTS_FUTURE.md](TTS_FUTURE.md) — deferred Qwen3-TTS integration notes. Reference this before proposing any TTS work; the user has explicitly accepted CPU-only slowness and wants Qwen3-TTS (not OpenAI TTS / edge-tts / etc.) when the time comes.
- [.env.example](.env.example) — template. `.env` itself is gitignored and holds `OPENAI_API_KEY` and `LLM_MODEL`.

## When adding features

- Keep it one file. Don't split app.py into modules unless the user asks.
- Use `@st.cache_resource` for anything expensive to construct (models, clients). Existing patterns: `load_whisper`, `load_openai`.
- New state goes in `st.session_state` and is initialized in `init_state()`.
