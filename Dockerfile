# syntax=docker/dockerfile:1

# Based on Docker's Python guide https://docs.docker.com/language/python/

ARG PYTHON_VERSION=3.12.4
FROM python:${PYTHON_VERSION}-slim as base

# Prevents Python from writing pyc files.
ENV PYTHONDONTWRITEBYTECODE=1

# Keeps Python from buffering stdout and stderr to avoid situations where
# the application crashes without emitting any logs due to buffering.
ENV PYTHONUNBUFFERED=1

# Add curl and git to template.
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

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

# Create required directories with proper permissions
RUN mkdir -p /app/logs && chmod 777 /app/logs && \
    mkdir -p /app/data && chmod 744 /app/data && \
    mkdir -p /home/appuser/.config && \
    mkdir -p /home/appuser/.config/git && \
    touch /home/appuser/.gitconfig && \
    chown -R appuser:appuser /home/appuser

# Configure git
RUN git config --system http.sslVerify false && \
    git config --system safe.directory /app

# Download dependencies as a separate step to take advantage of Docker's caching.
RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=bind,source=requirements.txt,target=requirements.txt \
    python -m pip install -r requirements.txt

# Switch to the non-privileged user to run the application.
USER appuser

# Copy the source code into the container.
COPY . .

# Expose the port that the application listens on.
EXPOSE 8085

# Run the application.
CMD ["uvicorn", "app.main:app", "--host=0.0.0.0", "--port=8085", "--log-config", "logging.yaml", "--no-access-log"]
