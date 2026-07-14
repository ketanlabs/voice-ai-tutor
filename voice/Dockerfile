# Voice component (LiveKit agent worker)
FROM python:3.13-slim

# Build deps for the model runtimes (onnx/torch) used by VAD + turn detector.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN pip install --no-cache-dir uv

COPY pyproject.toml ./
COPY src ./src
RUN uv pip install --system --no-cache -e .

ENV PYTHONPATH=/app/src

# Prefetch VAD + turn-detector model weights into the image so the first call
# isn't slow. This command auto-discovers every installed livekit plugin.
# Non-fatal: if the model host is unreachable at build time, the models download
# lazily on first use instead (the container has network).
RUN python -m livekit.agents download-files || echo "model prefetch skipped; will fetch at runtime"

CMD ["python", "-m", "voice.agent", "start"]
