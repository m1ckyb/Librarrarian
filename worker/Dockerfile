# ====== BUILD STAGE ======
FROM python:3.14-alpine3.21 AS builder

WORKDIR /app

# Install build dependencies for compiling Python packages
RUN apk add --no-cache gcc musl-dev libffi-dev

# Copy the requirements file into the container
COPY worker/requirements.txt .

# Install the Python dependencies into a virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -r requirements.txt

# ====== RUNTIME STAGE ======
FROM python:3.14-alpine3.21

WORKDIR /app

# Install runtime dependencies (ffmpeg for transcoding, iputils for ping, curl for healthchecks)
# Add VAAPI support libraries for Intel hardware acceleration
RUN apk add --no-cache ffmpeg iputils curl libffi \
    libva libva-intel-driver intel-media-driver mesa-va-gallium

# Copy the virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Ensure Python output is unbuffered
ENV PYTHONUNBUFFERED=1

# Copy the transcode worker script into the container
COPY worker/transcode.py .

# Copy the centralized version file
COPY VERSION.txt .

# The command to run the application
CMD ["python3", "transcode.py"]