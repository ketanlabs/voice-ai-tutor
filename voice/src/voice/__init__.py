"""Voice component — the LiveKit agent worker for the Spanish tutor.

Two internal layers, kept separate so either can change independently:
  * pipeline.py  — (c) the voice/AI layer: STT/LLM/TTS/VAD/turn-detection wiring
  * tutor.py     — (b) the conversation layer: LinguaTutor coach + exercise tools
"""
