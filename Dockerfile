# syntax=docker/dockerfile:1

# Based on Docker's Python guide https://docs.docker.com/language/python/

ARG PYTHON_VERSION=3.12.4
FROM python:${PYTHON_VERSION}-slim as base

# Prevents Python from writing pyc files.
ENV PYTHONDONTWRITEBYTECODE=1

# Keeps Python from buffering stdout and stderr to avoid situations where
# the application crashes without emitting any logs due to buffering.
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Create a non-privileged user that the app will run under.
ARG UID=10001
RUN adduser \
    --disabled-password \
    --gecos "" \
    --home "/home/appuser" \
    --shell "/sbin/nologin" \
    --uid "${UID}" \
    appuser

# Install only the necessary packages and clean up in the same layer to reduce image size
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create required directories with proper permissions
RUN mkdir -p /app/logs /app/data/codebase /home/appuser/.config/git \
    && touch /home/appuser/.gitconfig \
    && chown -R appuser:appuser /home/appuser /app/logs /app/data \
    && chmod 755 /app/logs /app/data /app/data/codebase

# Configure git with secure defaults
RUN git config --system http.sslVerify true \
    && git config --system safe.directory /app

# Download dependencies as a separate step to take advantage of Docker's caching.
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements.txt

# Copy the source code into the container.
COPY --chown=appuser:appuser . .

# Switch to the non-privileged user to run the application.
USER appuser

# Expose the port that the application listens on.
EXPOSE 8085

# Run the application.
CMD ["uvicorn", "app.main:app", "--host=0.0.0.0", "--port=8085", "--log-config", "logging.yaml", "--no-access-log"]
