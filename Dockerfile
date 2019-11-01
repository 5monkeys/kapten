###############################################################################
# BUILDER STEP
###############################################################################
FROM python:3.8-buster AS builder

# Extra Python environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/app/venv/bin:$PATH \
    PIP_NO_CACHE_DIR=1 \
    PIP_PIP_VERSION=19.3.1

# Setup the virtualenv
RUN python -m venv /app/venv
WORKDIR /app

# Install source code
# hadolint ignore=DL3013
COPY setup.py README.md ./
COPY kapten kapten
RUN set -x && \
    pip install pip==$PIP_PIP_VERSION && \
    pip install .["server"] && \
    pip check

###############################################################################
# RUNTIME STEP
###############################################################################
FROM python:3.8-slim-buster AS runtime

# Python environment settings and dpendency versions
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/app/venv/bin:$PATH \
    XDG_CACHE_HOME=/tmp/pip/.cache \
    APT_MAKE_VERSION=4.2.1-*

# Setup app user and directory
RUN set -x && \
    groupadd -g 8000 kapten && \
    useradd -r -u 8000 -g kapten -m -d /app -k /dev/null kapten && \
    chown -R kapten:kapten /app

# Install system dependencies
RUN set -x && \
    apt-get update && \
    apt-get install --no-install-recommends -y \
    make=$APT_MAKE_VERSION

# Install source code
USER kapten
WORKDIR /app
COPY --from=builder /app/venv venv

EXPOSE 8800

ENTRYPOINT ["kapten"]
