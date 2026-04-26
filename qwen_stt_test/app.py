import io
import os
import wave

import numpy as np
import streamlit as st
import whisper
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from streamlit_mic_recorder import mic_recorder

load_dotenv()

LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
SYSTEM_PROMPT = "You are a concise voice assistant. Reply in 1-3 sentences."
WHISPER_SR = 16000
WHISPER_MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")


WHISPER_SIZES = ["tiny", "base", "small"]


@st.cache_resource(show_spinner="Loading Whisper...")
def load_whisper(name: str):
    return whisper.load_model(name, download_root=WHISPER_MODEL_DIR)


@st.cache_resource
def load_chat_model():
    return init_chat_model(LLM_MODEL, model_provider="openai")


def init_state():
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if "mic_turn" not in st.session_state:
        st.session_state.mic_turn = 0


def wav_bytes_to_mono16k(wav_bytes: bytes) -> np.ndarray:
    """Decode a WAV blob to a mono float32 numpy array at 16 kHz without ffmpeg."""
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        n_channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        frame_rate = wf.getframerate()
        raw = wf.readframes(wf.getnframes())

    if sample_width == 1:
        audio = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    elif sample_width == 2:
        audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    elif sample_width == 4:
        audio = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
    else:
        raise ValueError(f"Unsupported WAV sample width: {sample_width}")

    if n_channels > 1:
        audio = audio.reshape(-1, n_channels).mean(axis=1)

    if frame_rate != WHISPER_SR and len(audio) > 0:
        new_len = int(round(len(audio) * WHISPER_SR / frame_rate))
        audio = np.interp(
            np.linspace(0, len(audio) - 1, new_len, dtype=np.float64),
            np.arange(len(audio), dtype=np.float64),
            audio,
        ).astype(np.float32)

    return np.ascontiguousarray(audio, dtype=np.float32)


def transcribe(wav_bytes: bytes, model) -> str:
    audio = wav_bytes_to_mono16k(wav_bytes)
    result = model.transcribe(audio, fp16=False)
    return result["text"].strip()


def main():
    st.set_page_config(page_title="Voice Chat (STT + LLM)", page_icon=":microphone:")
    st.title("Voice Chat")
    st.caption("Push-to-talk -> Whisper tiny -> " + LLM_MODEL + " (text only; TTS deferred)")

    init_state()

    with st.sidebar:
        st.subheader("Session")
        st.write("LLM:", f"`{LLM_MODEL}`")
        whisper_size = st.selectbox(
            "STT model (whisper)",
            WHISPER_SIZES,
            index=0,
            help="Larger = better quality, slower on CPU. First-time pick downloads weights into models/.",
            key="whisper_size",
        )
        if st.button("Clear chat", use_container_width=True):
            st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            st.session_state.mic_turn += 1
            st.rerun()

    whisper_model = load_whisper(whisper_size)
    chat_model = load_chat_model()

    for msg in st.session_state.messages:
        if msg["role"] == "system":
            continue
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    audio = mic_recorder(
        start_prompt="Record",
        stop_prompt="Stop",
        just_once=True,
        use_container_width=False,
        format="wav",
        key=f"mic_{st.session_state.mic_turn}",
    )

    if audio and audio.get("bytes"):
        with st.spinner("Transcribing..."):
            user_text = transcribe(audio["bytes"], whisper_model)

        if not user_text:
            st.warning("Did not catch any speech. Please try again.")
            st.session_state.mic_turn += 1
            st.rerun()

        st.session_state.messages.append({"role": "user", "content": user_text})

        with st.spinner("Thinking..."):
            resp = chat_model.invoke(st.session_state.messages)
            reply = resp.content

        st.session_state.messages.append({"role": "assistant", "content": reply})
        st.session_state.mic_turn += 1
        st.rerun()


if __name__ == "__main__":
    main()
