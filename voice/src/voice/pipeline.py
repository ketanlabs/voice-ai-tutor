"""(c) The voice/AI layer: assemble the STT/LLM/TTS/VAD/turn-detection pipeline.

Kept separate from the conversation logic (tutor.py) so providers can be swapped
— or the whole thing moved to LiveKit Inference — without touching pedagogy.
Provider selection is driven entirely by env via `config.Settings`.
"""
from __future__ import annotations

import logging

from livekit.agents import AgentSession, inference

from .config import Settings

logger = logging.getLogger("voice.pipeline")


def load_vad():
    """Load Silero VAD (called in prewarm so it's ready before the first turn)."""
    from livekit.plugins import silero

    return silero.VAD.load()


# --- bring-your-own-keys builders (direct plugins) ---------------------------
def _build_stt(cfg: Settings, language: str):
    if cfg.stt_provider == "deepgram":
        from livekit.plugins import deepgram

        # language='multi' lets the learner mix their native tongue and target lang.
        return deepgram.STT(model=cfg.stt_model, language="multi")
    if cfg.stt_provider == "openai":
        from livekit.plugins import openai

        # OpenAI transcription (e.g. gpt-4o-mini-transcribe), biased to the target language.
        return openai.STT(model=cfg.stt_model, language=language)
    raise ValueError(
        f"Unsupported STT_PROVIDER={cfg.stt_provider!r}. Use deepgram or openai, "
        "or set USE_LIVEKIT_INFERENCE=true."
    )


def _build_llm(cfg: Settings):
    from livekit.plugins import anthropic

    if cfg.llm_provider != "anthropic":
        raise ValueError(f"Unsupported LLM_PROVIDER={cfg.llm_provider!r} for the self-hosted path")
    return anthropic.LLM(model=cfg.llm_model)


def _build_tts(cfg: Settings, language: str):
    if cfg.tts_provider == "cartesia":
        from livekit.plugins import cartesia

        kwargs = {"model": cfg.tts_model, "language": language}
        if cfg.tts_voice_id:
            kwargs["voice"] = cfg.tts_voice_id
        return cartesia.TTS(**kwargs)
    if cfg.tts_provider == "openai":
        from livekit.plugins import openai

        # gpt-4o-mini-tts is multilingual and speaks the target language from the text.
        kwargs = {"model": cfg.tts_model}
        if cfg.tts_voice_id:
            kwargs["voice"] = cfg.tts_voice_id
        return openai.TTS(**kwargs)
    raise ValueError(
        f"TTS_PROVIDER={cfg.tts_provider!r} is not wired. Use cartesia or openai, "
        "or set USE_LIVEKIT_INFERENCE=true."
    )


# --- LiveKit Inference builders (single key, via Cloud) ----------------------
def _build_inference(cfg: Settings, language: str):
    stt = inference.STT(model=f"{cfg.stt_provider}/{cfg.stt_model}", language="multi")
    tts_kwargs = {"model": f"{cfg.tts_provider}/{cfg.tts_model}", "language": language}
    if cfg.tts_voice_id:
        tts_kwargs["voice"] = cfg.tts_voice_id
    tts = inference.TTS(**tts_kwargs)
    turn = inference.TurnDetector()
    # LiveKit Inference has no Anthropic models, so keep Claude via the direct
    # plugin when LLM_PROVIDER=anthropic; otherwise route the LLM through Inference.
    if cfg.llm_provider == "anthropic":
        llm = _build_llm(cfg)
    else:
        llm = inference.LLM(model=cfg.llm_model)
    return stt, llm, tts, turn


def build_session(cfg: Settings, vad, language: str = "es") -> AgentSession:
    """Construct the AgentSession for the chosen target language + provider path."""
    if cfg.use_livekit_inference:
        logger.info(
            "building pipeline via LiveKit Inference (lang=%s, llm=%s)",
            language, cfg.llm_provider,
        )
        stt, llm, tts, turn = _build_inference(cfg, language)
    else:
        logger.info(
            "building self-hosted pipeline: lang=%s stt=%s llm=%s(%s) tts=%s",
            language, cfg.stt_provider, cfg.llm_provider, cfg.llm_model, cfg.tts_provider,
        )
        from livekit.plugins.turn_detector.multilingual import MultilingualModel

        stt = _build_stt(cfg, language)
        llm = _build_llm(cfg)
        tts = _build_tts(cfg, language)
        turn = MultilingualModel()

    return AgentSession(stt=stt, llm=llm, tts=tts, vad=vad, turn_detection=turn)
