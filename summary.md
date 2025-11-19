# Project Summary - 2025-11-19

This document summarizes the significant progress made on the Transcode Cluster project. We have evolved the project from a set of local Python scripts into a fully containerized, continuously integrated, and robust distributed system.

## 1. Version Control and Initial Setup

- **Secured Credentials**: Removed hardcoded database passwords from Python scripts and configured them to use environment variables for improved security.
- **Git Repository**: Established a clean Git repository by creating a `.gitignore` file to exclude unnecessary files (like virtual environments and cache).
- **Published to GitHub**: Walked through the process of initializing a Git repository and publishing the project to GitHub.

## 2. Project Documentation

- **`README.md`**: Created a comprehensive `README.md` file detailing the project's purpose, features, architecture, setup instructions, and command-line usage for both the worker and the dashboard.

## 3. Containerization with Docker

- **Dashboard Container**: The Flask web dashboard (`dashboard_app.py`) was fully containerized.
  - A `Dockerfile` was created to define the image, including Python dependencies and the Gunicorn web server.
  - A `.dockerignore` file was added to keep the Docker image lean.
- **Worker Container**: The transcoding worker (`transcode.py`) was also containerized.
  - A separate `Dockerfile.worker` was created, which includes the installation of `ffmpeg`.
  - This allows workers to be deployed on any machine with Docker, without manual dependency installation.

## 4. CI/CD with GitHub Actions

- **Automated Image Publishing**: Set up two GitHub Actions workflows:
  - `docker-publish.yml`: Automatically builds the `transcode-dashboard` image and publishes it to the GitHub Container Registry (GHCR) on every push to the `main` branch.
  - `docker-publish-worker.yml`: Automatically builds the `transcode-worker` image and publishes it to GHCR.
- This creates a full Continuous Integration/Continuous Deployment pipeline for the container images.

## 5. Orchestration with Docker Compose

- **`docker-compose.yml`**: Created a Docker Compose file to define and manage the entire application stack with a single command.
- **Services Defined**:
  - `dashboard`: Runs the Flask web application.
  - `worker`: Runs the transcoding script.
  - `db`: Runs a PostgreSQL 13 database.
- **Configuration**:
  - Uses a `.env` file to manage secrets like the database password.
  - Configures persistent data for the PostgreSQL database using a Docker volume (`postgres_data`).
  - Mounts a local `./media` folder into the worker container for processing.

## 6. Dashboard UI/UX Enhancements

- **Dynamic Updates**: The dashboard UI was converted from a static, page-reloading interface to a dynamic one. It now uses JavaScript's `fetch` API to poll a new `/api/status` endpoint and update the content every 5 seconds without a full refresh.
- **Error Management**:
  - Added a "View Errors" button that opens a modal dialog.
  - The modal displays a detailed list of all failed transcodes, including the reason, timestamp, and a "View Log" button.
  - The "View Log" button expands to show the full, raw `ffmpeg` output for easy debugging.
  - Added a "Clear Errors" button to truncate the `failed_files` table after confirmation.
- **History View**:
  - Added a "History" tab to the dashboard.
  - This tab displays a list of the last 100 successfully encoded files, showing the filename, which node processed it, the size reduction, and the date.

## 7. Worker Enhancements & Bug Fixes

- **Continuous Watch Mode**: The worker script was converted from a one-off script into a continuous service. It now:
  - Scans the entire media folder.
  - If it processes files, it immediately re-scans for more.
  - If it finds no files to process, it waits for 60 seconds before starting a new scan.
- **Self-Updating Mechanism**:
  - The worker now checks a `version.txt` file in the GitHub repository on startup.
  - If a newer version is found, it prompts the user for permission to download the latest `transcode.py` and overwrite itself.
- **Advanced Error Handling**:
  - **Stream Selection**: Fixed a critical bug where `ffmpeg` would fail on files with multiple video streams (e.g., a movie file with embedded cover art). The script now intelligently selects the video stream with the highest resolution.
  - **CPU Fallback**: Fixed a bug where low-resolution videos would crash hardware encoders. The script now detects this specific error and automatically re-attempts the transcode using the more compatible CPU encoder.
- **Schema Migration**: Made the database initialization more robust. The worker now automatically adds missing columns (`log`, `version`) to existing tables on startup, preventing crashes after an update.
- **Centralized Logging**:
  - **Success Logging**: Successful transcodes are now logged to a new `encoded_files` table in the database.
  - **Failure Logging**: Instead of writing crash reports to local text files, the worker now saves the complete `ffmpeg` error log directly to the `failed_files` table in the database.

## 8. Codebase and Project Structure

- **Project Restructuring**: The project was reorganized into a clean, modular structure with `dashboard/` and `worker/` subdirectories, each containing its own `Dockerfile` and `requirements.txt`.
- **Versioning**: Implemented a clear versioning scheme (`0.3.0`), which is now displayed for each worker in the dashboard UI, providing better visibility into the cluster's state.