# Use a Python image that includes OS build tools
FROM python:3.13-slim-bullseye

# Set non-interactive frontend for package installers
ENV DEBIAN_FRONTEND=noninteractive

# Install ffmpeg from the OS package manager
RUN apt-get update && apt-get install -y ffmpeg && apt-get clean

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install the Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the worker script into the container
COPY transcode.py .