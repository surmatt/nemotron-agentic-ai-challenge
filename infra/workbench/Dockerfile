# Public image for the visual pipeline workbench (nemotron-challenge ui).
# Build from the repository root:
#   docker buildx build --platform linux/amd64 -f infra/workbench/Dockerfile -t nemotron-workbench:local .
# The image holds no keys. Pass the .env values as environment variables at run time.

FROM node:22.20.0-bookworm-slim AS ui
WORKDIR /ui
COPY ui/package.json ui/package-lock.json ./
RUN npm ci
COPY ui/ ./
RUN npm run build

FROM python:3.12.12-slim-bookworm AS runtime
COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /usr/local/bin/uv

# Tectonic compiles the LaTeX documents. The archive checksum is pinned.
ARG TECTONIC_VERSION=0.17.0
ARG TECTONIC_SHA256=8533d07f9ccbd7a65824b9e0459041bca34af1eb33daba48f59215593753a3b7
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl fontconfig \
 && curl -fsSLo /tmp/tectonic.tgz "https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%40${TECTONIC_VERSION}/tectonic-${TECTONIC_VERSION}-x86_64-unknown-linux-musl.tar.gz" \
 && echo "${TECTONIC_SHA256}  /tmp/tectonic.tgz" | sha256sum -c - \
 && tar -xzf /tmp/tectonic.tgz -C /usr/local/bin tectonic \
 && rm /tmp/tectonic.tgz && apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

RUN useradd --uid 10001 --create-home app
WORKDIR /app
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 PYTHONUNBUFFERED=1 PATH=/app/.venv/bin:$PATH

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --extra ui --no-install-project
COPY src/ src/
COPY docs/evaluation/ docs/evaluation/
COPY templates/ templates/
RUN uv sync --locked --no-dev --extra ui

COPY --from=ui /ui/dist ui/dist
# Saved corpus run and the pinned scans. The workbench shows them read-only.
ARG ARTIFACTS_DIR=artifacts-e2e3
COPY ${ARTIFACTS_DIR}/ artifacts/
COPY data/raw/britannica/ data/raw/britannica/
RUN chown -R app:app /app

USER app
# Fill the tectonic package cache, so the first document step does not wait for downloads.
RUN cd /tmp && printf '%s\n' '\documentclass{article}' '\usepackage[utf8]{inputenc}' '\usepackage[T1]{fontenc}' \
      '\usepackage[margin=2cm]{geometry}' '\usepackage{hyperref}' '\begin{document}warm\end{document}' > warm.tex \
 && tectonic --chatter minimal warm.tex && rm -f warm.*

EXPOSE 8790
CMD ["nemotron-challenge", "ui", "--host", "0.0.0.0", "--port", "8790", "--work-dir", "artifacts"]
