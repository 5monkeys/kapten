###############################################################################
# BUILDER STEP
###############################################################################
FROM python:3.8-buster AS builder

# Extra Python environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/app/venv/bin:$PATH

# Setup the virtualenv
RUN python -m venv /app/venv
WORKDIR /app

# Pinned versions
ENV PIP_NO_CACHE_DIR=1 \
    PIP_PIP_VERSION=19.3.1 \
    PIP_PIP_TOOLS_VERSION=4.2.0

# hadolint ignore=DL3013
RUN set -x && \
    pip install pip==$PIP_PIP_VERSION pip-tools==$PIP_PIP_TOOLS_VERSION && \
    # Use uvloop master til 3.8 working release exists
    pip install Cython && \
    pip install git+https://github.com/MagicStack/uvloop && \
    pip install starlette uvicorn && \
    pip check

# Install source code
RUN mkdir /app/src
WORKDIR /app/src
COPY setup.py README.md ./
COPY kapten kapten
RUN pip install -e .

###############################################################################
# RUNTIME STEP
###############################################################################
FROM python:3.8-slim-buster AS runtime

# Extra Python environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/app/venv/bin:$PATH \
    XDG_CACHE_HOME=/tmp/pip/.cache

# Setup app user and directory
RUN set -x && \
    groupadd -g 8000 app && \
    useradd -r -u 8000 -g app app && \
    mkdir /app && \
    chown -R app:app /app

# Install source code
USER app
WORKDIR /app
COPY --from=builder /app/venv venv
COPY --from=builder /app/src src

ENTRYPOINT ["kapten"]
