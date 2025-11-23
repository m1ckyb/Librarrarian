# CodecShift

**CodecShift** is a distributed video transcoding cluster. It allows multiple computers (nodes) to work together to process a library of video files, converting them to the more efficient HEVC (H.265) codec. The entire system is containerized and managed with Docker Compose for easy deployment.

## Features

*   **Distributed Transcoding:** Run worker nodes on multiple machines to process files in parallel.
*   **Hardware Acceleration:** Automatically detects and uses NVIDIA (NVENC) and Intel (VAAPI) for fast transcoding, with a fallback to CPU.
*   **Centralized Web Dashboard:** A Flask-based UI for real-time monitoring and management.
    *   **Full Remote Control**: Start, stop, pause, and resume individual worker nodes from the dashboard.
    *   **Live Stats & History**: View aggregate statistics and a searchable, paginated history of all transcodes.
    *   **Health Indicators**: At-a-glance node health status based on heartbeat activity.
    *   **Error Management**: View detailed logs for failed transcodes and clear them from the queue.
*   **Database-Driven Coordination:** A central PostgreSQL database manages node status, job history, and all worker configurations.
*   **Dynamic Configuration:** All worker settings, from quality levels to file extensions, are configurable in real-time via the "Options" tab in the UI.
*   **Containerized & Automated**: The entire stack is orchestrated with Docker Compose, and images are automatically built and published via GitHub Actions.

## How It Works

The system consists of three core services, all managed by Docker Compose:

1.  **`db`**: A PostgreSQL database that acts as the single source of truth. It stores the job queue, node status, configuration, and history.
2.  **`dashboard`**: The central brain of the cluster. It scans the media library, creates a job queue, assigns jobs to available workers, and provides the web interface for monitoring and management.
3.  **`worker`**: A "dumb" but powerful transcoding engine. It connects to the dashboard, requests a job, completes the transcode, reports the result, and repeats. It no longer scans the filesystem itself.

## Deployment with Docker Compose

This is the recommended method for running CodecShift.

### 1. Prerequisites
*   Docker and Docker Compose installed on your system.
*   A Personal Access Token (PAT) from GitHub with the `read:packages` scope. This is required to pull the container images from the GitHub Container Registry (GHCR).

### 2. Configuration
1.  **Clone the repository:**
    ```bash
    git clone https://github.com/m1ckyb/CluserEncode.git
    cd CodecShift
    ```

2.  **Create an environment file:**
    Create a file named `.env` in the project root. This file will store your database credentials.
    ```env
    # .env
    # --- Database Settings ---
    POSTGRES_DB=codecshift
    POSTGRES_USER=transcode
    POSTGRES_PASSWORD=your_super_secret_password
    ```

3.  **Edit `docker-compose.yml`:**
    Open the `docker-compose.yml` file and replace `your-github-username` with your actual GitHub username in the `image` definitions for the `dashboard` and `worker` services.

### 3. Running the Cluster
1.  **Log in to GHCR:**
    You only need to do this once. Use your GitHub username and the Personal Access Token you created as the password.
    ```bash
    docker login ghcr.io -u YOUR-GITHUB-USERNAME -p YOUR-PERSONAL-ACCESS-TOKEN
    ```

2.  **Start the cluster:**
    Place your video files in the `media` directory and start the application stack.
    ```bash
    docker-compose up -d
    ```

3.  **Access the Dashboard:**
    Open a web browser and navigate to `http://localhost:5000`. You should see the CodecShift dashboard. From here, you can go to the "Options" tab to configure settings and then start your worker nodes.

### Scaling the Cluster
To add more processing power, you can scale the number of worker services. For example, to run 3 workers:
```bash
docker-compose up -d --scale worker=3
```