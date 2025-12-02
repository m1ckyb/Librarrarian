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

# Install runtime dependencies (iputils for ping, curl for healthchecks, tzdata for timezone support, postgresql-client for pg_dump)
RUN apk add --no-cache iputils curl libffi tzdata postgresql-client

# Copy the virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy the entire dashboard directory and the root VERSION.txt file
COPY dashboard/ .
COPY VERSION.txt .

# Expose the port the app runs on
EXPOSE 5000

# The command to run the application using Gunicorn (a production-ready web server)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--log-level", "debug", "--error-logfile", "-", "--capture-output", "dashboard_app:app"]