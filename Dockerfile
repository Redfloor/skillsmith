# Hermetic build/runtime image. Uses the official uv image so no system Python or
# Node is required. Multi-stage: deps are resolved from the committed lockfile.
#
# NOTE: Docker is used here only as a build/distribution convenience. It is NOT
# treated as a security boundary for running untrusted skill code — that is the
# sandbox layer's job (gVisor / Firecracker / bubblewrap). See docs/self-healing.md.

# ---- builder ---------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_PREFERENCE=only-managed

WORKDIR /app

# Copy only what's needed to resolve deps first (better layer caching).
COPY pyproject.toml uv.lock .python-version ./
COPY packages ./packages

# Reproducible install from the lockfile.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --all-packages --no-dev

# ---- runtime ---------------------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime

# Sandbox fallbacks available inside the container (best-effort; microVM/gVisor
# are provided by the host, not here).
RUN apt-get update \
    && apt-get install -y --no-install-recommends bubblewrap git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /app /app
ENV PATH="/app/.venv/bin:${PATH}"

# Drop privileges.
RUN useradd --create-home --uid 10001 smith
USER smith

ENTRYPOINT ["skillsmith"]
CMD ["--help"]
