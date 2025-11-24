# CodecShift

**CodecShift** is a distributed video transcoding cluster that uses a central dashboard to manage a fleet of worker nodes. It integrates with your Plex Media Server to automatically find, queue, and transcode your video library to the efficient HEVC (H.265) codec. The entire system is containerized and managed with Docker Compose for easy deployment.

## Features

*   **Distributed Transcoding:** Run worker nodes on multiple machines to process files in parallel.
*   **Plex Integration:** Link your Plex account, select libraries, and let the dashboard automatically find and queue non-HEVC files.
*   **Hardware Acceleration:** Automatically detects and uses NVIDIA (NVENC), Intel (QSV/VAAPI), and Apple VideoToolbox for fast transcoding, with a fallback to CPU.
*   **Centralized Web Dashboard:** A Flask-based UI for real-time monitoring and management.
    *   **Full Remote Control**: Start, stop, and pause individual worker nodes.
    *   **Job Queue Management**: View the status of all pending, in-progress, and failed jobs.
    *   **Live Stats & History**: View aggregate statistics and a searchable history of all transcodes.
    *   **Error Management**: View detailed logs for failed transcodes.
*   **Database-Driven Coordination:** A central PostgreSQL database manages the job queue, node status, historical data, and all system configurations.
*   **Dynamic Configuration:** All settings—from Plex connections to transcoding quality—are configurable in real-time via the "Options" tab in the UI.
*   **Containerized & Automated**: The entire stack is orchestrated with Docker Compose, and images are automatically built and published via GitHub Actions.

## How It Works

The system consists of three core services, all managed by Docker Compose:

1.  **`db`**: A PostgreSQL database that acts as the single source of truth for the entire cluster.
2.  **`dashboard`**: The central brain. It connects to Plex, scans for files, builds a job queue, assigns jobs to workers, and provides the web UI for management.
3.  **`worker`**: A "dumb" but powerful transcoding engine. It connects to the dashboard, requests a job, performs the transcode using FFmpeg, reports the result, and repeats.

## Deployment with Docker Compose

This is the recommended method for running CodecShift.

### 1. Prerequisites
*   Docker and Docker Compose installed.
*   A GitHub account to pull the container images.

### 2. Configuration
1.  **Clone the repository:**
    ```bash
    git clone https://github.com/m1ckyb/ClusterEncode.git
    cd ClusterEncode
    ```

2.  **Create an environment file:**
    Create a file named `.env` in the project root. This file stores your database credentials and a secret key for the web application's session management.
    ```env
    # .env
    # --- Database Settings ---
    POSTGRES_DB=codecshift
    POSTGRES_USER=transcode
    POSTGRES_PASSWORD=your_super_secret_password

    # --- Web Application Secret ---
    # Generate a random string for this, e.g., by running: openssl rand -hex 32
    FLASK_SECRET_KEY=your_flask_secret_key
    
    # --- Authentication Settings (Optional) ---
    # Master switch to enable authentication features.
    AUTH_ENABLED=false
    
    # OIDC Provider Settings (if AUTH_ENABLED is true)
    OIDC_ENABLED=false
    OIDC_ISSUER_URL=https://your-provider.com/auth/realms/your-realm
    OIDC_CLIENT_ID=your-client-id
    OIDC_CLIENT_SECRET=your-client-secret
    OIDC_PROVIDER_NAME=Authentik # Optional: The display name for your OIDC provider
    
    # Local Login Settings (if AUTH_ENABLED is true)
    LOCAL_LOGIN_ENABLED=false
    LOCAL_USER=admin
    # The password must be base64 encoded. To generate, run: echo -n 'your_password' | base64
    LOCAL_PASSWORD=eW91cl9zdXBlcl9zZWNyZXRfcGFzc3dvcmQ=
    ```

### 3. Running the Cluster
1.  **Log in to GHCR:**
    You only need to do this once. Use your GitHub username and a Personal Access Token (PAT) with `read:packages` scope as the password.
    ```bash
    docker login ghcr.io -u YOUR_GITHUB_USERNAME
    ```

2.  **Start the cluster:**
    Place your video files in the `media` directory and start the application stack.
    ```bash
    docker-compose up -d
    ```

3.  **Access the Dashboard:**
    Open a web browser and navigate to `http://localhost:5000`. You should see the CodecShift dashboard. From here, you can go to the "Options" tab to configure settings and then start your worker nodes.
    - **Configure Plex**: In the "Options" tab, enter your Plex server URL and link your account. Once linked, you can select which libraries to monitor for transcoding.

### Scaling the Cluster
To add more processing power, you can scale the number of worker services. For example, to run 3 workers:
```bash
docker-compose up -d --scale worker=3 --no-recreate
```