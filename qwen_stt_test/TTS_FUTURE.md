# Deferred: Qwen3-TTS integration

This is the planned follow-up to add spoken-voice output to `app.py`. The current app
is voice-in / text-out only. Add TTS once the HuggingFace download is possible
(at home, not on the work network).

Reference: https://github.com/QwenLM/Qwen3-TTS

## Why deferred

- Qwen3-TTS 1.7B local model download is ~3-5 GB from HuggingFace.
- HF is blocked on the work network; must be downloaded at home first.
- Inference on CPU is slow (tens of seconds to minutes per utterance). The user
  explicitly accepted this trade-off.

## Dependency additions

```bash
# Install CPU-only torch FIRST, otherwise `qwen-tts` will pull the CUDA wheel.
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install qwen-tts soundfile
```

Also add to `requirements.txt`:

```
qwen-tts
soundfile
```

(Leave `torch` out of `requirements.txt` so the CPU index-url is used manually.)

## Model choice

`Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice` — has 9 preset speakers, no reference audio needed.

If 1.7B is too slow, fall back to `Qwen/Qwen3-TTS-12Hz-0.6B-Base` (smaller but needs a
reference voice prompt).

## Loader (cache so it only loads once per Streamlit process)

```python
import torch
from qwen_tts import Qwen3TTSModel

@st.cache_resource(show_spinner="Loading Qwen3-TTS (CPU, first run is slow)...")
def load_tts():
    return Qwen3TTSModel.from_pretrained(
        "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
        device_map="cpu",
        dtype=torch.float32,
    )
```

## Inference + Streamlit audio playback

```python
import io
import soundfile as sf

wavs, sr = tts.generate_custom_voice(
    text=reply,
    language=language,   # e.g. "English"
    speaker=speaker,     # e.g. "Ryan"
)
buf = io.BytesIO()
sf.write(buf, wavs[0], sr, format="WAV")
st.audio(buf.getvalue(), format="audio/wav", autoplay=True)
```

## Sidebar controls to add to `app.py`

```python
SPEAKERS = ["Vivian", "Serena", "Uncle_Fu", "Dylan", "Eric",
            "Ryan", "Aiden", "Ono_Anna", "Sohee"]
LANGUAGES = ["Auto", "English", "Chinese", "Japanese", "Korean",
             "German", "French", "Russian", "Portuguese", "Spanish", "Italian"]

speaker = st.sidebar.selectbox("Voice", SPEAKERS, index=SPEAKERS.index("Ryan"))
language = st.sidebar.selectbox("Language", LANGUAGES, index=LANGUAGES.index("English"))
```

Preset speaker -> native language hint:

| Speaker   | Native language   |
|-----------|-------------------|
| Vivian    | Chinese           |
| Serena    | Chinese           |
| Uncle_Fu  | Chinese           |
| Dylan     | Chinese (Beijing) |
| Eric      | Chinese (Sichuan) |
| Ryan      | English           |
| Aiden     | English           |
| Ono_Anna  | Japanese          |
| Sohee     | Korean            |

## Where to plug it into `app.py`

Right after appending the assistant message and rendering the bubble:

```python
with st.chat_message("assistant"):
    st.markdown(reply)
    with st.spinner("Synthesizing voice..."):
        wavs, sr = tts.generate_custom_voice(text=reply, language=language, speaker=speaker)
    buf = io.BytesIO()
    sf.write(buf, wavs[0], sr, format="WAV")
    st.audio(buf.getvalue(), format="audio/wav", autoplay=True)
```

## HF cache location (for backup / pre-seeding across machines)

```
%USERPROFILE%\.cache\huggingface\hub\models--Qwen--Qwen3-TTS-12Hz-1.7B-CustomVoice
```

Copy this folder between machines to avoid re-downloading.

## Manual smoke test BEFORE wiring into Streamlit

```bash
python -c "import torch; from qwen_tts import Qwen3TTSModel; m=Qwen3TTSModel.from_pretrained('Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice', device_map='cpu', dtype=torch.float32); w,sr=m.generate_custom_voice(text='hello world', language='English', speaker='Ryan'); import soundfile as sf; sf.write('out.wav', w[0], sr); print('ok', sr)"
```

If `out.wav` plays the sentence in Ryan's voice, the TTS path is ready to wire in.
