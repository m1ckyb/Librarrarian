# Transcode Cluster

This project creates a distributed video transcoding cluster. Multiple computers (nodes) can work together to process a library of video files, converting them to the more efficient HEVC (H.265) codec. It's designed to be resilient, leveraging a central PostgreSQL database for job coordination and status tracking, with a web-based dashboard for monitoring.

## Features

*   **Distributed Transcoding:** Run worker scripts on multiple machines to process files in parallel.
*   **Hardware Acceleration:** Automatically detects and uses NVIDIA (NVENC) and Intel (VAAPI) for fast transcoding, with a fallback to CPU.
*   **Job Coordination:** A file-based locking mechanism prevents multiple nodes from working on the same file.
*   **Failure Tracking:** Failed transcodes are logged to the database to prevent repeated attempts on problematic files.
*   **Web Dashboard:** A Flask-based web interface provides a real-time view of the cluster's status, including active nodes, current progress, and total failed files.
*   **Flexible Configuration:** Easily configure quality settings, file size minimums, and hardware preferences.

## How It Works

The system consists of two main components:

1.  **Worker (`transcode.py`):** This is the script you run on each machine that will perform the transcoding. It scans a specified folder for video files, checks if they need to be processed (i.e., not already HEVC, not in the failure list), and then uses `ffmpeg` to convert them. It continuously reports its status (heartbeat) to a central database.

2.  **Web Dashboard (`dashboard_app.py`):** This is a simple Flask web application that queries the database to display the status of all active worker nodes and a count of failed jobs.

A **PostgreSQL** database acts as the central brain, storing information about active nodes, their current tasks, and a list of files that have failed to transcode.

## Requirements

*   Python 3
*   `ffmpeg` installed and available in your system's PATH.
*   A PostgreSQL database server accessible from all nodes.
*   Python libraries: `psycopg2-binary`, `Flask`.

## Setup

### 1. Database Setup

On your PostgreSQL server, you need to create a database and a user for the cluster.

```sql
CREATE DATABASE transcode_cluster;
CREATE USER transcode WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE transcode_cluster TO transcode;
```

The necessary tables (`active_nodes`, `failed_files`) will be created automatically the first time a worker script is run.

### 2. Application Setup

1.  **Clone the repository:**
    ```bash
    git clone <your-repository-url>
    cd CluserEncode
    ```

2.  **Install Python dependencies:**
    It's recommended to create a `requirements.txt` file for this.
    ```
    Flask
    psycopg2-binary
    ```
    Then install them:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configure Database Connection:**
    Both `transcode.py` and `dashboard_app.py` are configured to read database credentials from environment variables for security. You can also change the default values directly in the scripts if you are running this on a private, secure network.

    **`transcode.py`:**
    ```python
    DB_CONFIG = {
        "host": "192.168.10.120", 
        "user": "transcode",
        "password": "password", # Change this or use environment variables
        "dbname": "transcode_cluster"
    }
    ```

    **`dashboard_app.py`:**
    This script is already set up to prioritize environment variables.
    *   `DB_HOST`
    *   `DB_USER`
    *   `DB_PASSWORD`
    *   `DB_NAME`

## Usage

### Running the Worker Node (`transcode.py`)

Open a terminal on each machine you want to use as a worker and run the `transcode.py` script, pointing it to your media folder.

**Example:**

Scan a folder recursively and process all files larger than 500MB.
```bash
# On Linux/macOS
python3 transcode.py "/path/to/your/videos" -R --min 0.5

# On Windows
python transcode.py "C:\Path\to\your\videos" -R --min 0.5
```

**Common Arguments:**
*   `folder`: The root folder to scan for videos.
*   `-R`, `--recursive`: Scan all subdirectories within the root folder.
*   `--min <GB>`: Skip files smaller than the specified size in gigabytes (e.g., `--min 1.5`).
*   `--force-nvidia`: Force the use of NVIDIA's NVENC encoder.
*   `--force-vaapi`: Force the use of Intel's VAAPI encoder.
*   `--force-cpu`: Force the use of CPU-based encoding (slow).
*   `--debug`: Show verbose logging about why files are being skipped.

### Running the Web Dashboard (`dashboard_app.py`)

The dashboard provides a visual overview of the cluster. Before running, set the database password as an environment variable.

**On Windows (Command Prompt):**
```powershell
set DB_PASSWORD=your_secure_password
flask run --host=0.0.0.0 --port=5000
```

**On Linux/macOS:**
```bash
export DB_PASSWORD="your_secure_password"
flask run --host=0.0.0.0 --port=5000
```

Now you can open a web browser and navigate to `http://<your-machine-ip>:5000` to see the dashboard.