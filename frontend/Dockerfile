# Frontend (Next.js) — multi-stage: builder (also used by `make test`) + slim runner.
FROM node:20-alpine AS builder
WORKDIR /app

# Install all deps (incl. devDependencies for building + tests).
COPY package.json package-lock.json* ./
RUN npm ci

COPY . .

# NEXT_PUBLIC_* values are inlined into the client bundle at BUILD time, so they
# must be provided as build args (compose passes them from .env).
ARG NEXT_PUBLIC_LIVEKIT_URL
ARG NEXT_PUBLIC_BACKEND_URL
ENV NEXT_PUBLIC_LIVEKIT_URL=$NEXT_PUBLIC_LIVEKIT_URL
ENV NEXT_PUBLIC_BACKEND_URL=$NEXT_PUBLIC_BACKEND_URL
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# --- runner: minimal standalone server ---
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000
CMD ["node", "server.js"]
