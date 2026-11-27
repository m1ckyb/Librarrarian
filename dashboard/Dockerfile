# ====== BUILD STAGE ======
FROM python:3.14-alpine3.21 AS builder

WORKDIR /app

# Install build dependencies for compiling Python packages
RUN apk add --no-cache gcc musl-dev libffi-dev

# Copy the requirements file from the dashboard directory
COPY dashboard/requirements.txt .

# Install the Python dependencies into a virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -r requirements.txt

# ====== RUNTIME STAGE ======
FROM python:3.14-alpine3.21

WORKDIR /app

# Install runtime dependencies (ffmpeg for internal scanner ffprobe, iputils for ping, curl for healthchecks, tzdata for timezone support, postgresql-client for pg_dump)
RUN apk add --no-cache ffmpeg iputils curl libffi tzdata postgresql-client \
    && adduser -D -u 1000 appuser \
    && mkdir -p /data/backup \
    && chown -R appuser:appuser /app /data

# Copy the virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy the entire dashboard directory and the root VERSION.txt file
COPY --chown=appuser:appuser dashboard/ .
COPY --chown=appuser:appuser VERSION.txt .

# Run as non-root user
USER appuser

# Expose the port the app runs on
EXPOSE 5000

# Run Gunicorn with 1 process and 8 threads so in-process background threads stay coordinated without blocking concurrent HTTP requests
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--worker-class", "gthread", "--threads", "8", "--timeout", "120", "--log-level", "info", "--error-logfile", "-", "--capture-output", "dashboard_app:app"]