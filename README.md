# Librarrarian

**Librarrarian** is a distributed video transcoding cluster that automatically converts your media library to modern, space-efficient video codecs. It uses a central web dashboard to orchestrate a fleet of worker nodes, intelligently distributing the workload across multiple machines. The system integrates deeply with Plex Media Server, Jellyfin, and the Arr suite (Sonarr, Radarr, Lidarr) to provide a complete media management solution. Everything is containerized with Docker Compose for simple deployment and scaling.

## Table of Contents
- [What It Does](#what-it-does)
- [How It Works](#how-it-works)
- [Key Components](#key-components)
- [Features](#features)
- [Architecture](#architecture)
- [Deployment with Docker Compose](#deployment-with-docker-compose)
- [Configuration Guide](#configuration-guide)
- [Hardware Acceleration](#hardware-acceleration)
- [Security](#security)
- [Common Workflows](#common-workflows)
- [Scaling the Cluster](#scaling-the-cluster)
- [Troubleshooting](#troubleshooting)
- [Development](#development)
- [FAQ](#faq)
- [Performance Benchmarks](#performance-benchmarks)
- [Acknowledgments](#acknowledgments)
- [Contributing](#contributing)
- [Support](#support)
- [Changelog](#changelog)
- [License](#license)

## What It Does

Librarrarian is your automated media transcoding solution. Here's what it handles for you:

**Media Transcoding**
- Automatically converts video files to HEVC (H.265) or AV1 codecs, reducing file sizes by 40-70% while maintaining quality
- Intelligently detects which files need transcoding and which can be skipped
- Supports distributed processing across multiple machines for faster completion
- Uses hardware acceleration (NVIDIA, Intel, Apple) when available for 5-10x faster transcoding

**Media Discovery**
- Integrates with Plex and Jellyfin to automatically discover and queue your media libraries
- Built-in media scanner as an alternative to Plex for standalone operation
- Finds and queues files based on codec, resolution, and quality settings

**Arr Integration** (Sonarr, Radarr, Lidarr)
- **Rename Scans**: Identifies files that don't conform to naming standards and queues rename jobs
- **Quality Scans**: Finds episodes that don't meet quality profile cutoffs for upgrade consideration
- **Auto-Rename**: Automatically renames files after transcoding to reflect new codec information
- Keeps your media collection organized and properly named

**File Maintenance**
- Finds and safely removes stale `.lock` and `.tmp_*` files left by crashed processes
- Cleanup jobs require manual approval for safety

**Centralized Management**
- Web-based dashboard for monitoring all workers and jobs in real-time
- Remote control of worker nodes (start/stop/pause/resume)
- View live transcoding progress with FPS and speed metrics
- Searchable history of all transcodes with space savings statistics

## Key Components

Librarrarian consists of three core services that work together:

### 1. Dashboard (The Control Center)
A Flask-based web application that serves as the brain of the operation:
- **Web UI**: Real-time monitoring, configuration, and control interface
- **Job Scheduler**: Manages the queue and assigns work to available workers
- **Media Scanners**: Integrates with Plex or scans directories directly to find files
- **Background Threads**: Handles long-running scans without blocking the UI
- **API Server**: Provides RESTful endpoints for worker communication

### 2. Worker (The Processing Engine)
A Python script that does the heavy lifting:
- Requests jobs from the dashboard
- Performs video transcoding using FFmpeg
- Reports progress in real-time (percentage, FPS, speed)
- Handles hardware acceleration detection and configuration
- Processes rename operations via Arr APIs
- Cleans up stale temporary files

### 3. Database (The Single Source of Truth)
A PostgreSQL database that stores:
- Job queue (pending, in-progress, completed, failed)
- Worker node status and heartbeats
- Transcoding history and statistics
- System configuration and settings
- Media source configurations (libraries, folders, path mappings)

## Features

### Transcoding & Processing
*   **Distributed Processing**: Scale across multiple machines to transcode in parallel
*   **Hardware Acceleration**: Automatic detection and use of NVIDIA NVENC, Intel QSV/VAAPI, and Apple VideoToolbox
*   **Intelligent Codec Detection**: Skip files already in target codec
*   **Quality Control**: Configurable CRF/CQ values per encoder and resolution
*   **Multi-Format Support**: Process movies, TV shows, music videos, and more

### Media Discovery & Integration
*   **Plex Integration**: Deep integration with Plex Media Server
    *   OAuth-based account linking via PIN code
    *   Dynamic library selection
    *   Automatic path mapping support
*   **Jellyfin Integration**: Full support for Jellyfin as a media source
    *   API Key based authentication
    *   Dynamic library selection
    *   Path mapping support
*   **Internal Scanner**: Built-in media scanner using ffprobe
    *   Scan specific subdirectories
    *   No Plex dependency required
*   **Arr Suite Integration** (Sonarr, Radarr, Lidarr):
    *   Connection testing and validation
    *   Rename scanning with approval workflow
    *   Quality mismatch detection
    *   Auto-rename after transcode
    *   Manual or automated operation modes

### Dashboard & Monitoring
*   **Real-Time Status**: Live view of all worker nodes and their current jobs
*   **Full Remote Control**: Start, stop, pause, and resume workers individually
*   **Job Queue Management**:
    *   Filter by type (transcode, cleanup, rename, quality mismatch)
    *   Filter by status (pending, encoding, failed, etc.)
    *   Delete individual jobs or clear entire queue
    *   Release cleanup/rename jobs from approval status
*   **Progress Tracking**: Real-time progress bars with file counts, FPS, and speed
*   **Statistics Dashboard**: Total files encoded, space saved, average reduction
*   **Searchable History**: Full log of all transcodes with pagination
*   **Failed Job Management**: View error logs and retry or delete failed jobs
*   **Live Updates**: Dashboard auto-refreshes without page reloads
*   **Estimated Finish Time (ETA)**: See the estimated completion time for in-progress transcodes.

### Configuration & Control
*   **Web-Based Configuration**: All settings managed through the UI
*   **Dynamic Settings**: Changes take effect without restarting services
*   **Advanced Options**: Hide complexity with Standard/Advanced/All view modes
*   **Path Mapping**: Handle different mount points between dashboard and workers
*   **Media Path Validation**: Configurable allowed directories for security
*   **Theme Support**: Light, dark, and system-default themes

### Tools & Maintenance
*   **Manual Scans**: Trigger media or Arr scans on demand
*   **Cancellable Operations**: Stop long-running scans from the UI
*   **Stale File Cleanup**: Find and remove leftover temporary files
*   **Data Export**: Backup all settings and configurations to JSON
*   **Database Backups**: Automated daily backups with configurable retention, plus manual backup and restore options.
*   **Version Mismatch Detection**: Alerts when workers and dashboard are out of sync

### Security & Authentication
*   **Optional Authentication**: Enable for production deployments
*   **OIDC Support**: Integration with enterprise identity providers
*   **Local Login**: Username/password fallback option
*   **API Key Authentication**: Secure worker-to-dashboard communication
*   **Dev Mode**: Bypass auth for local development
*   **Configurable SSL Verification**: Support for self-signed certificates in dev

### Deployment & Operations
*   **Docker Compose**: Simple orchestration of all services
*   **Automatic Migrations**: Database schema updates automatically on startup
*   **Health Checks**: Proper service dependency management
*   **Volume Persistence**: Database and history preserved across restarts
*   **Timezone Configuration**: Set container timezone for accurate timestamps
*   **Pre-built Images**: Available from GitHub Container Registry
*   **CI/CD Pipeline**: Automated builds and testing

## How It Works

### The Workflow

**1. Discovery Phase**
```
Media Scanner → Plex API / File System → Codec Detection → Job Queue
```
The dashboard scans your media (via Plex integration or direct file system scanning) and identifies files that need transcoding based on their current codec. Files already in the target format (HEVC/AV1) are skipped.

**2. Job Distribution**
```
Dashboard → PostgreSQL Job Queue → Available Worker Nodes
```
When a worker requests work, the dashboard assigns the next pending job from the queue. Multiple workers can process different jobs simultaneously, enabling parallel transcoding.

**3. Transcoding**
```
Worker → FFmpeg + Hardware Acceleration → Progress Updates → Dashboard
```
The worker downloads the job details, sets up the FFmpeg command with appropriate hardware acceleration, and begins transcoding. Every few seconds, it reports progress (percentage complete, FPS, speed) back to the dashboard.

**4. Completion**
```
Worker → Replace Original File → Update Database → Dashboard Notification
```
When transcoding finishes successfully, the worker replaces the original file with the new one, logs the result to the history table (including file sizes and space saved), and marks the job as complete.

**5. Next Job**
```
Worker → Request Next Job → Repeat
```
The worker immediately requests another job and the cycle continues until the queue is empty or the worker is stopped.

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        Web Browser                              │
│                     (User Interface)                            │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTPS/HTTP
┌────────────────────────────▼────────────────────────────────────┐
│                      Dashboard Service                          │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐      │
│  │  Flask Web   │  │  Background  │  │  REST API       │      │
│  │     UI       │  │   Threads    │  │  (Workers)      │      │
│  └──────────────┘  └──────────────┘  └─────────────────┘      │
│         │                  │                   │                │
│         │                  │                   │                │
│  ┌──────▼──────────────────▼───────────────────▼─────────┐    │
│  │            PostgreSQL Connection Pool                   │    │
│  └──────────────────────────┬──────────────────────────────┘    │
└─────────────────────────────┼───────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────┐
│                    PostgreSQL Database                          │
│  ┌────────────┐ ┌──────────┐ ┌─────────┐ ┌──────────────────┐ │
│  │ Job Queue  │ │  Nodes   │ │ History │ │ Worker Settings  │ │
│  └────────────┘ └──────────┘ └─────────┘ └──────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │ SQL Queries
            ┌─────────────────┼─────────────────┐
            │                 │                 │
┌───────────▼──────┐ ┌────────▼─────────┐ ┌────▼──────────────┐
│  Worker Node 1   │ │  Worker Node 2   │ │  Worker Node N    │
│ ┌──────────────┐ │ │ ┌──────────────┐ │ │ ┌──────────────┐  │
│ │ Transcode.py │ │ │ │ Transcode.py │ │ │ │ Transcode.py │  │
│ └──────┬───────┘ │ │ └──────┬───────┘ │ │ └──────┬───────┘  │
│        │         │ │        │         │ │        │          │
│ ┌──────▼───────┐ │ │ ┌──────▼───────┐ │ │ ┌──────▼───────┐  │
│ │    FFmpeg    │ │ │ │    FFmpeg    │ │ │ │    FFmpeg    │  │
│ │   + NVENC    │ │ │ │   + QSV      │ │ │ │   + CPU      │  │
│ └──────────────┘ │ │ └──────────────┘ │ │ └──────────────┘  │
└──────────────────┘ └──────────────────┘ └───────────────────┘

External Integrations:
┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│ Plex Server │  │ Jellyfin Server │  │   Sonarr    │  │   Radarr    │  │   Lidarr    │
└─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘
       ▲                ▲                ▲                ▲
       └────────────────┴────────────────┴────────────────┘
                         Dashboard APIs
```

### Asynchronous Design

To prevent timeouts and ensure UI responsiveness:

- **Long-running operations** (media scans, Arr scans) run in background threads
- **API endpoints** return immediately after queuing the operation
- **Progress polling** allows the UI to show real-time status updates
- **Event-driven architecture** uses threading.Event for inter-thread communication
- **Non-blocking background workers** handle multiple concurrent scans

## Deployment with Docker Compose

This is the **recommended and officially supported** method for running Librarrarian. The entire stack (dashboard, workers, database) is orchestrated with a single command.

### 1. Prerequisites

**Required:**
*   **Docker** (20.10 or higher) and **Docker Compose** (v2.0 or higher)
*   **GitHub account** to authenticate with GitHub Container Registry (GHCR)
*   **Media library** accessible on the host system

**Hardware Recommendations:**
*   **Dashboard**: Minimal resources (1 CPU, 512MB RAM)
*   **Worker**: At least 2 CPU cores and 2GB RAM per worker
*   **Database**: Minimal resources (1 CPU, 512MB RAM, 10GB storage)
*   **For hardware acceleration**: NVIDIA GPU, Intel with Quick Sync, or Apple Silicon

**Operating System:**
*   Linux (Ubuntu, Debian, Fedora, etc.)
*   macOS (with Docker Desktop)
*   Windows (with Docker Desktop and WSL2)

### 2. Configuration
1.  **Clone the repository:**
    ```bash
    git clone https://github.com/m1ckyb/Librarrarian.git
    cd Librarrarian
    ```

2.  **Create an environment file:**
    Create a file named `.env` in the project root. This file stores your database credentials and a secret key for the web application's session management.
    ```env
    # .env
    # --- Database Settings ---
    DB_NAME=librarrarian
    DB_USER=transcode
    DB_PASSWORD=your_super_secret_password

    # --- Web Application Secret ---
    # Generate a random string for this, e.g., by running: openssl rand -hex 32
    FLASK_SECRET_KEY=your_flask_secret_key
    
    # --- General Settings ---
    # Set the timezone for the containers, e.g., 'Australia/Sydney', 'America/New_York'
    TZ=UTC

    # --- API Key for Worker Authentication ---
    # This is required if AUTH_ENABLED is true. Generate a secure random string.
    # e.g., openssl rand -hex 32
    API_KEY=your_worker_api_key

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
    
    # --- Worker Settings (Optional) ---
    # If true, workers will automatically start processing jobs
    AUTOSTART=false
    
    # Comma-separated list of allowed base directories for media files
    # This is used for security validation to prevent path traversal attacks
    # Default: /media
    # Example for NFS mounts: MEDIA_PATHS=/media,/nfs/media,/mnt/storage
    MEDIA_PATHS=/media
    ```

### 3. Running the Cluster

1.  **Log in to GHCR:**
    You only need to do this once. Use your GitHub username and a [Personal Access Token (PAT)](https://github.com/settings/tokens) with `read:packages` scope as the password.
    ```bash
    docker login ghcr.io -u YOUR_GITHUB_USERNAME
    ```
    When prompted for a password, paste your PAT.

2.  **Place your media:**
    The `docker-compose.yml` file expects your media to be in a `./media` directory relative to the compose file. You can modify this path in the compose file if needed:
    ```yaml
    volumes:
      - /path/to/your/actual/media:/media
    ```

3.  **Start the cluster:**
    ```bash
    docker-compose up -d
    ```
    This will:
    - Pull the latest images from GHCR
    - Create a PostgreSQL database with the schema
    - Start the dashboard on port 5000
    - Start one worker node

4.  **Verify the services are running:**
    ```bash
    docker-compose ps
    ```
    All services should show as "Up" and healthy.

5.  **Access the Dashboard:**
    Open your web browser and navigate to:
    ```
    http://localhost:5000
    ```
    
    If authentication is enabled (`AUTH_ENABLED=true`), you'll be prompted to log in.

## Configuration Guide

### First-Time Setup

Once you've accessed the dashboard, complete these steps:

#### 1. Configure Media Sources (Choose One or Both)

**Option A: Plex Integration**
1. Navigate to the **Options** tab
2. Click on the **Integrations** sub-tab
3. Select the **Plex** tab
4. Click **"Link Plex Account"**
5. Visit `plex.tv/link` and enter the PIN code shown
6. Once linked, your Plex libraries will appear
7. Select which libraries to monitor
8. Configure path mapping if needed (see [Path Mapping](#path-mapping))

**Option B: Jellyfin Integration**
1. Navigate to the **Options** tab
2. Click on the **Integrations** sub-tab
3. Select the **Jellyfin** tab
4. Click **"Link Server"**
5. Enter your Jellyfin Server URL and API Key
6. Once linked, your Jellyfin libraries will appear
7. Select which libraries to monitor
8. Configure path mapping if needed (see [Path Mapping](#path-mapping))

**Option C: Internal Scanner**
1. Navigate to the **Options** tab → **Integrations** → **Internal**
2. Your `/media` subdirectories will be listed
3. Assign a media type to each folder (TV Shows, Movies, etc.)
4. Folders set to "None (Ignore)" will be skipped

#### 2. Configure Arr Integrations (Optional)

For each Arr application you want to integrate:

1. Go to **Options** → **Integrations** → **Sonarr/Radarr/Lidarr**
2. Enable the integration
3. Enter the **Host** (e.g., `http://sonarr:8989`)
4. Enter your **API Key** (found in Arr settings)
5. Click **"Test Connection"** to verify
6. Configure additional options:
   - **Create Rename Jobs in Queue**: Require approval before renaming
   - **Auto-Rename After Transcode**: Automatically rename after encoding

#### 3. Configure Transcoding Settings

1. Navigate to **Options** → **Transcoding & System**
2. Select your **Encoder Priority** (Auto, NVIDIA, Intel, CPU)
3. Set **Quality Values** (CRF/CQ) for different encoders and resolutions
   - Lower = better quality, larger files (recommended: 23-28)
   - Higher = worse quality, smaller files
4. Choose which codecs are eligible for re-encoding:
   - Enable **HEVC (H.265)** to skip already-encoded HEVC files
   - Enable **AV1** to also skip AV1 files
   - Enable **VP9** to include VP9 in the transcode queue

#### 4. Start Workers

1. Go to the **Dashboard** (main page)
2. Find your worker node card
3. Click the **"Start"** button
4. The worker will begin requesting and processing jobs

### Path Mapping

Path mapping handles different mount points between the dashboard and workers.

**When to use it:**
- Dashboard runs in Docker, workers run on bare metal
- Different servers with different mount points
- Network shares (NFS, SMB) with different paths

**Example Scenario:**
```
Dashboard container sees:  /media/movies/
Worker sees:               /mnt/nas/movies/
```

**Configuration:**
1. Go to **Options** → **Integrations** → **Plex** (or Internal)
2. Enable **"Path Mapping"**
3. Set **From** (container path): `/media`
4. Set **To** (worker path): `/mnt/nas`

The system will automatically translate paths when assigning jobs.

## Hardware Acceleration

Librarrarian automatically detects and uses hardware acceleration when available. This can speed up transcoding by 5-10x compared to CPU encoding.

### NVIDIA GPUs (NVENC)

**Requirements:**
- NVIDIA GPU with NVENC support (GTX 1050 or newer)
- NVIDIA drivers installed on host
- Docker configured for GPU support

**Setup:**
1. Install [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)
2. Edit `docker-compose.yml` and uncomment the NVIDIA section:
   ```yaml
   librarrarian-worker-1:
     deploy:
       resources:
         reservations:
           devices:
             - driver: nvidia
               count: 1
               capabilities: [gpu, compute, video]
   ```
3. Restart the worker: `docker-compose up -d`

**Verification:**
- Check worker logs for "NVENC encoder available"
- During transcoding, GPU usage should be visible in `nvidia-smi`

### Intel Quick Sync (QSV)

**Requirements:**
- Intel CPU with Quick Sync support (6th gen or newer)
- `/dev/dri` devices available

**Setup:**
The `docker-compose.yml` includes this by default:
```yaml
devices:
  - /dev/dri:/dev/dri
```

**Verification:**
- Check worker logs for "QSV encoder available"
- On the host, run: `ls -la /dev/dri` to verify devices exist

### Apple VideoToolbox

**Requirements:**
- macOS with Apple Silicon (M1/M2/M3) or recent Intel Mac
- Docker Desktop for Mac

**Note:** VideoToolbox acceleration works automatically on macOS. The worker will detect it and use it when available.

### Troubleshooting Hardware Acceleration

**GPU not detected:**
```bash
# Check if devices are accessible in the container
docker exec librarrarian-worker-1 ls -la /dev/dri
docker exec librarrarian-worker-1 nvidia-smi
```

**Permission issues:**
```bash
# Add user to video/render groups on host
sudo usermod -a -G video,render $USER
```

## Security

### Authentication

Librarrarian supports multiple authentication methods:

**1. OIDC (Recommended for Production)**
- Integrates with Authentik, Keycloak, Azure AD, Google, etc.
- Supports SSO and centralized user management
- Configure via `OIDC_*` environment variables

**2. Local Login**
- Username and base64-encoded password
- Simple fallback for small deployments
- Configure via `LOCAL_USER` and `LOCAL_PASSWORD` variables

**3. API Key Authentication**
- Required for worker-to-dashboard communication
- Set the same `API_KEY` value for dashboard and all workers

**Disabling Authentication (Development Only):**
```env
AUTH_ENABLED=false
```
**Never disable authentication in production or on internet-facing deployments.**

### Best Practices

1. **Use strong, random values** for all secrets:
   ```bash
   openssl rand -hex 32  # Generate random keys
   ```

2. **Enable SSL/TLS verification** in production:
   ```env
   ARR_SSL_VERIFY=true
   OIDC_SSL_VERIFY=true
   ```

3. **Run behind a reverse proxy** (nginx, Traefik, Caddy):
   - Enables HTTPS
   - Provides rate limiting
   - Adds additional security headers

4. **Restrict network access**:
   - Use firewall rules to limit access to trusted networks
   - Don't expose ports 5432 (database) to the internet
   - Consider VPN for remote access

5. **Regular updates**:
   ```bash
   docker-compose pull
   docker-compose up -d
   ```

For detailed security information, see [SECURITY.md](SECURITY.md).

## Common Workflows

### Workflow 1: Initial Media Library Transcode

**Goal**: Convert your entire existing media library to HEVC.

1. **Configure your media source** (Plex or Internal Scanner)
2. **Adjust quality settings** in Options → Transcoding
3. **Run a manual scan**:
   - Job Queue tab → "Manual Scan" button
   - Check "Force" to re-queue everything
4. **Start your workers**
5. **Monitor progress** on the Dashboard
6. **Check history** for space savings statistics

**Tip**: Start with a small test library first to dial in your quality settings.

### Workflow 2: Automated Ongoing Transcoding

**Goal**: Automatically transcode new media as it's added.

1. **Configure Plex integration** with library monitoring
2. **Enable automatic scanning** (or use Plex webhooks)
3. **Set workers to autostart**:
   ```env
   AUTOSTART=true
   ```
4. **Let it run** - new files will be queued and processed automatically

### Workflow 3: Sonarr Integration for TV Shows

**Goal**: Keep TV show filenames consistent with Sonarr naming.

1. **Configure Sonarr** in Options → Integrations → Sonarr
2. **Enable "Create Rename Jobs in Queue"** for approval workflow
3. **Enable "Auto-Rename After Transcode"**
4. **Run a rename scan** from Tools → Sonarr
5. **Review and release** rename jobs from the Job Queue
6. **Monitor** as files are renamed via Sonarr API

### Workflow 4: Multi-Server Distributed Transcoding

**Goal**: Use multiple machines to speed up processing.

1. **Set up dashboard** on your main server
2. **Deploy additional workers** on other machines:
   ```bash
   # On worker machine, modify docker-compose.yml to only run worker
   docker-compose up -d librarrarian-worker-1
   ```
3. **Configure path mapping** if mount points differ
4. **Start all workers**
5. **Jobs automatically distribute** across all available workers

### Workflow 5: Cleanup After System Crash

**Goal**: Remove stale lock and temp files.

1. Go to **Tools** tab
2. Click **"Scan for Stale Files"** under Cleanup
3. Review the queued cleanup jobs
4. Click **"Release All Cleanup Jobs"**
5. Workers will delete the stale files

## Scaling the Cluster

### Adding More Workers

**Method 1: Scale with Docker Compose**
```bash
docker-compose up -d --scale librarrarian-worker-1=3 --no-recreate
```
This creates 3 instances of the same worker service.

**Method 2: Add Named Workers**
Edit `docker-compose.yml`:
```yaml
librarrarian-worker-2:
  image: ghcr.io/m1ckyb/librarrarian-worker:0.11.2
  container_name: librarrarian-worker-2
  hostname: librarrarian-worker-2
  # ... same config as worker-1 ...
  
librarrarian-worker-3:
  image: ghcr.io/m1ckyb/librarrarian-worker:0.11.2
  container_name: librarrarian-worker-3
  hostname: librarrarian-worker-3
  # ... same config as worker-1 ...
```
Then run: `docker-compose up -d`

**Method 3: Separate Machines**
1. Copy the `docker-compose.yml` to another machine
2. Remove the `librarrarian` and `db` services (keep only worker)
3. Update `DASHBOARD_URL` to point to your main server
4. Ensure `API_KEY` matches
5. Run: `docker-compose up -d`

### Performance Considerations

- **CPU-bound**: More workers = faster completion
- **I/O-bound**: Too many workers on same disk can cause slowdowns
- **Network**: For network storage (NAS), consider workers on different machines
- **GPU**: Each worker can utilize one GPU efficiently

## Troubleshooting

### Dashboard Won't Start

**Symptom**: Dashboard container exits immediately
```bash
docker-compose logs librarrarian
```

**Common Causes:**
1. **Database not ready**: Wait for health check to pass
2. **Invalid environment variables**: Check `.env` file syntax
3. **Port conflict**: Another service using port 5000
   ```bash
   # Change port in docker-compose.yml
   ports:
     - "5001:5000"
   ```

### Workers Not Getting Jobs

**Symptoms**: Workers show as "Idle" but jobs are pending

**Checklist:**
1. **Is the queue paused?** Check Dashboard for "Resume Queue" button
2. **Are workers started?** Click "Start" on each worker card
3. **API key mismatch?** Verify `API_KEY` matches in dashboard and worker
4. **Authentication error?** Check worker logs for 401/403 errors
5. **Version mismatch?** Dashboard will show warning if versions differ

### Transcoding Fails Immediately

**Symptom**: Jobs move to "Failed" status quickly

**Diagnosis:**
1. Click **"View Errors"** in the Dashboard header
2. Find the failed file in the list
3. Check the error message

**Common Issues:**
- **File not found**: Path mapping misconfiguration
- **Permission denied**: File ownership/permission issues
- **Codec not supported**: FFmpeg missing required libraries
- **Hardware acceleration failed**: Falls back to CPU encoding

**Solutions:**
```bash
# Check file permissions on host
ls -la /path/to/media

# Fix permissions if needed
sudo chown -R 1000:1000 /path/to/media

# Check worker logs
docker logs librarrarian-worker-1
```

### Path Mapping Issues

**Symptom**: "No such file or directory" errors

**Diagnosis:**
The dashboard container path doesn't match the worker's real path.

**Solution:**
1. Determine where media is mounted:
   - Dashboard: Check in Options → Integrations
   - Worker: `docker exec librarrarian-worker-1 ls /media`
2. Configure path mapping in Options
3. Test with a single file

### Database Issues

**Symptom**: "relation does not exist" or connection errors

**Fresh Start:**
```bash
docker-compose down -v  # WARNING: Deletes all data
docker-compose up -d
```

**Backup First:**
```bash
docker exec librarrarian-db pg_dump -U transcode librarrarian > backup.sql
```

### High Memory Usage

**Symptom**: System slowdown, OOM killer terminating processes

**Solutions:**
1. **Reduce concurrent workers**
2. **Add resource limits** to docker-compose.yml:
   ```yaml
   librarrarian-worker-1:
     deploy:
       resources:
         limits:
           memory: 2G
           cpus: '2'
   ```
3. **Adjust FFmpeg buffer size** (requires modifying worker code)

### Slow Transcoding Performance

**Checklist:**
1. **Hardware acceleration enabled?** Check worker logs
2. **Multiple workers on same disk?** I/O bottleneck
3. **Quality settings too high?** Lower CRF values = slower encoding
4. **Old hardware?** Consider GPU upgrade or more workers

### Plex Integration Not Working

**Symptom**: "Test Connection" fails or libraries don't appear

**Solutions:**
1. **Re-link Plex account**: Options → Integrations → Plex
2. **Check Plex URL**: Must be accessible from dashboard container
3. **Firewall**: Ensure port 32400 is accessible
4. **Plex Server version**: Update to latest version

### Arr Integration Failures

**Symptom**: Connection test fails or scans don't find files

**Solutions:**
1. **Verify URL format**: Include `http://` and port (e.g., `http://sonarr:8989`)
2. **Check API key**: Found in Arr Settings → General
3. **Network connectivity**: Ensure services can reach each other
4. **SSL verification**: Set `ARR_SSL_VERIFY=false` for self-signed certs (dev only)

### UI Not Updating

**Symptom**: Dashboard shows stale data

**Solutions:**
1. **Hard refresh**: Ctrl+Shift+R (or Cmd+Shift+R on Mac)
2. **Check browser console**: F12 → Console tab for JavaScript errors
3. **Restart dashboard**:
   ```bash
   docker-compose restart librarrarian
   ```

### Getting Help

If you're still stuck:

1. **Check logs**:
   ```bash
   docker-compose logs librarrarian
   docker-compose logs librarrarian-worker-1
   ```

2. **Enable debug mode** (if available in your version):
   ```bash
   docker exec librarrarian-worker-1 python transcode.py --debug
   ```

3. **Open an issue** on GitHub with:
   - Your `docker-compose.yml` (remove sensitive data)
   - Relevant log excerpts
   - Steps to reproduce the issue
   - Your environment (OS, Docker version, hardware)
## Development

### Local Development

For development, use the development compose file which builds images locally:

```bash
# Build and start services
docker-compose -f docker-compose-dev.yml build
docker-compose -f docker-compose-dev.yml up -d

# View logs
docker-compose -f docker-compose-dev.yml logs -f

# Stop services
docker-compose -f docker-compose-dev.yml down
```

### Project Structure

```
Librarrarian/
├── dashboard/              # Flask web application
│   ├── dashboard_app.py    # Main application logic
│   ├── templates/          # Jinja2 HTML templates
│   ├── static/             # CSS, JavaScript, images
│   └── Dockerfile
├── worker/                 # Transcoding worker
│   ├── transcode.py        # Worker script
│   └── Dockerfile
├── docker-compose.yml      # Production deployment
├── docker-compose-dev.yml  # Development deployment
├── VERSION.txt             # Single source of version truth
├── README.md               # This file
├── remember.md             # Architectural patterns and decisions
├── summary.md              # High-level project summary
├── CHANGELOG.md            # Release history
├── unreleased.md           # Upcoming changes
└── SECURITY.md             # Security guidelines
```

### Making Changes

1. **Update code** in `dashboard/` or `worker/`
2. **Test locally** with `docker-compose-dev.yml`
3. **Update documentation** in `unreleased.md`
4. **Run security checks** before committing
5. **Submit pull request** with clear description

### Database Migrations

When adding new database columns or tables:

1. Increment `TARGET_SCHEMA_VERSION` in `dashboard_app.py`
2. Add migration SQL to the `MIGRATIONS` dictionary
3. Use idempotent SQL (`IF NOT EXISTS`, `ON CONFLICT`)
4. Test on a fresh database

Example:
```python
TARGET_SCHEMA_VERSION = 5
MIGRATIONS = {
    5: [
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS new_field TEXT;",
        "INSERT INTO worker_settings (setting_name, setting_value) "
        "VALUES ('new_setting', 'default') ON CONFLICT DO NOTHING;"
    ]
}
```

## FAQ

### Q: Can I transcode from HEVC to AV1?
**A:** Yes! Enable HEVC in the "Codecs eligible for re-encoding" settings. This tells the system to re-encode HEVC files instead of skipping them.

### Q: Will this work with 4K HDR content?
**A:** Partially. The transcoding will work, but HDR metadata may not be preserved correctly. This is a known limitation of FFmpeg's HEVC encoder in some configurations. Test with a sample file first.

### Q: Can I pause/resume the entire cluster?
**A:** Yes, use the "Pause Queue" button on the Dashboard. This prevents new jobs from being assigned, but workers will finish their current job.

### Q: What happens if a worker crashes mid-job?
**A:** The job will show as "Encoding" until force removed (after 10 minutes). The dashboard can't detect a crashed worker immediately, so use the "Force Remove" button to clean up.

### Q: Can I run multiple workers on the same machine?
**A:** Yes! Scale with `docker-compose up -d --scale librarrarian-worker-1=3` or add additional named worker services.

### Q: Does this work with music files?
**A:** The transcoding engine is video-focused. While you can scan music video libraries, don't use this for audio-only files (MP3, FLAC, etc.).

### Q: Can I use this without Plex?
**A:** Yes! Use the Internal Scanner to scan directories directly. Plex integration is completely optional.

### Q: How do I update to a new version?
```bash
docker-compose pull
docker-compose up -d
```
Database migrations run automatically on startup.

### Q: Can I change the transcoding quality after jobs are queued?
**A:** Settings changes affect new jobs only. To re-queue with new settings, clear the queue and run a manual scan with "Force" enabled.

### Q: What's the best CRF value?
**A:** Start with 23-25 for most content:
- **23**: High quality, larger files
- **25**: Balanced quality/size (recommended)
- **28**: Lower quality, smaller files

Test with sample files to find your preference.

### Q: Can I preserve the original files?
**A:** Not currently. The worker replaces the original file with the transcoded version. Make backups before running if you're concerned.

### Q: Does this work on ARM processors (Raspberry Pi)?
**A:** The Docker images are x86_64 only. ARM support would require:
1. Multi-arch Docker images
2. FFmpeg compiled for ARM
3. Hardware acceleration for ARM (V4L2)

This is not currently implemented.

## Performance Benchmarks

Approximate transcoding speeds (1080p content, 23-28 CRF):

| Hardware | Speed | Notes |
|----------|-------|-------|
| Intel i7-12700K (QSV) | 120-180 FPS | 12th gen, Quick Sync |
| NVIDIA RTX 3060 (NVENC) | 150-250 FPS | 12GB VRAM |
| Apple M1 (VideoToolbox) | 80-120 FPS | 8-core |
| Intel i5-8400 (CPU) | 15-25 FPS | Software encoding |
| AMD Ryzen 9 5900X (CPU) | 25-40 FPS | 12-core |

**Variables affecting speed:**
- Source codec (H.264 → HEVC is faster than VP9 → HEVC)
- Resolution (4K takes 4x longer than 1080p)
- CRF value (lower = slower)
- Bitrate of source file
- Audio track complexity

## Acknowledgments

### Built With
- **[FFmpeg](https://ffmpeg.org/)** - The backbone of all transcoding operations
- **[Flask](https://flask.palletsprojects.com/)** - Web framework for the dashboard
- **[PostgreSQL](https://www.postgresql.org/)** - Reliable database for job coordination
- **[Docker](https://www.docker.com/)** - Containerization and orchestration
- **[Bootstrap](https://getbootstrap.com/)** - UI framework for the dashboard

### Inspired By
This project was inspired by the need for automated, distributed video transcoding in home media server environments, drawing ideas from various community projects and discussions around Plex, Sonarr, and media management automation.

## Contributing

Contributions are welcome! Here's how you can help:

1. **Report Bugs**: Open an issue with detailed reproduction steps
2. **Suggest Features**: Open an issue with your use case and requirements
3. **Submit Pull Requests**: 
   - Fork the repository
   - Create a feature branch
   - Make your changes with tests
   - Update documentation
   - Submit a PR with a clear description

Please read [SECURITY.md](SECURITY.md) for security-related contributions.

## Support

- **Issues**: [GitHub Issues](https://github.com/m1ckyb/Librarrarian/issues)
- **Discussions**: [GitHub Discussions](https://github.com/m1ckyb/Librarrarian/discussions)
- **Documentation**: This README and [remember.md](remember.md) for developers

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a detailed history of changes and releases.

## License

This project is provided as-is for personal and educational use. Please review the repository for any license information.

---

**Made with ❤️ for the media automation community**

