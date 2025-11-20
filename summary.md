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

## 9. Version 0.4.0 - Dashboard UI Enhancements

This version focused on improving the usability and information density of the web dashboard.

- **FPS Display**: The dashboard now shows the Frames Per Second (FPS) for each active transcoding node.
- **Dynamic Error Button**: The "View Errors" button is now green when there are no errors and red if errors are present.
- **Local Timestamp**: The "Updated" timestamp now reflects the user's local browser time.
- **Application Footer**: Added a footer to the dashboard containing the web UI version and a link to the project's GitHub repository.


## 10. Version 0.4.1 - Centralized Versioning & UI Polish

This version focused on improving project maintainability and refining the user interface.

- **Centralized Versioning**: To prevent version discrepancies between components, a single `VERSION.txt` file was created at the project root. The worker script (`transcode.py`) was updated to read its version from this file, ensuring consistency.
- **UI Polish**: The dashboard footer was enhanced with CSS to be fixed at the bottom of the viewport, using a semi-transparent background and a blur effect to create a modern "glassy" look.
- **Conditional UI Elements**: The dashboard was made smarter by hiding the "Clear Errors" button when the error count is zero, decluttering the interface.


## 11. Version 0.4.2 - Robustness and UI Fixes

This version addressed key usability and deployment flexibility issues.

- **Robust Worker Versioning**: The worker script (`transcode.py`) was improved to handle being run as a standalone file. It now attempts to read the `VERSION.txt` file, but if it fails (e.g., `FileNotFoundError`), it gracefully falls back to using `"standalone"` as its version identifier instead of crashing.
- **Dashboard Layout Fix**: Fixed a UI bug where the "glassy" fixed footer would overlap and obscure the "View Errors" button. Padding was added to the main body of the page to ensure all content remains accessible.


## 12. Version 0.5.0 - Into the Darkness: UI Theming and Layout

This version introduced a major user experience enhancement with a full theming system and significant frontend code refactoring.

- **UI Theme Switcher**: A theme switcher was added to the dashboard, allowing users to select between Light, Dark, and a System-default mode. The chosen theme is persisted in the browser's local storage.
- **Improved Footer Layout**: The footer was redesigned with a split layout, placing the version information on the bottom-left and the link to the GitHub project on the bottom-right.
- **Template Refactoring**: The frontend code was made more maintainable by introducing a `base.html` template. This base template now holds the common page structure, the new theme-switching logic, and the footer, while `index.html` extends it to render the main content.


## 13. Version 0.6.0 - Command & Control

This version introduced a powerful configuration system, allowing for dynamic control over worker behavior directly from the web UI.

- **Worker Options Page**: A new "Options" page was created in the dashboard, providing a user-friendly interface for changing worker settings.
- **Database-Driven Configuration**: A new `worker_settings` table was added to the database to store and persist configuration. The worker script was updated to create this table and populate it with default values if it doesn't exist.
- **Configurable Scan Behavior**:
  - **Rescan Delay**: Users can now set a delay (0-60 minutes) that workers will wait before starting a new scan after processing files.
  - **Folder Exclusion**: A toggle was added to enable or disable the skipping of any directory named `encoded`.
- **Dynamic Worker Logic**: The core worker loop was updated to fetch the latest settings from the database at the beginning of each full scan, allowing for real-time changes to the cluster's behavior without restarting any services.


## 14. Version 0.7.0 (Alpha) - The Boring & Broken Update

This release was primarily focused on fixing a cascade of bugs related to the previous feature releases, improving the stability and usability of both the worker and the dashboard.

- **Critical Bug Fixes**:
  - **Worker Rescan Delay**: Resolved a major bug where the worker would ignore the rescan delay set in the options and always default to a 60-second wait.
  - **Worker Self-Update**: The update check URL was corrected to point to the `develop` branch, fixing "404 Not Found" errors.
- **Dashboard Stability and Layout Fixes**:
  - **Session Crash**: Added a `secret_key` to the Flask application to prevent it from crashing when saving settings on the options page.
  - **Layout Correction**: Fixed numerous UI bugs, including the broken layout of active node cards and inconsistent headers, by moving the "Updated" timestamp and theme switcher into a globally consistent footer.
  - **Robustness**: The options page was improved to handle cases where the database settings have not yet been initialized by a worker, preventing it from crashing on a fresh deployment.

## 15. Version 0.7.1 (Alpha) - The Non-Interactive Fix

This small release addressed a critical usability bug with the worker's self-update feature when running inside Docker.

- **Non-Interactive Updates**: The worker's self-update prompt was removed in favor of a non-interactive system. An `--update` command-line flag was added to trigger the update automatically.
- **Docker Default Behavior**: The `docker-compose.yml` file was updated to include the `--update` flag in the worker's command, making automatic updates the default behavior for containerized deployments. This resolves a bug where the interactive prompt would fail due to terminal line-ending conflicts (`^M`) inside the container.


## 16. CI/CD Enhancements & Branching Strategy

- **Branching Model**: Implemented a Git branching model using `main` for production-ready code and `develop` for ongoing development.
- **Development Workflow**:
    - The GitHub Actions pipeline is now configured to trigger on every push to the `develop` branch.
    - This automatically builds and publishes the `dashboard` and `worker` images to GHCR with a `:develop` tag.
- **Release Workflow**:
    - Pushing to `main` no longer triggers a build. Instead, a new build is triggered only when a **new release is created** in GitHub.
    - When a release is created (e.g., `v1.0.0`), the pipeline builds and publishes images with two tags: the specific version number (e.g., `:v1.0.0`) and `:latest`.
- **Docker Compose Integration**:
    - The `docker-compose.yml` file was updated to pull pre-built images directly from GHCR instead of building them locally.
    - It is configured to use the `:latest` tag, ensuring that running `docker-compose up` deploys the most recent official release.

## 17. Version 0.7.2 (Alpha) - CSS Fixes

This version focused on fixing several CSS issues to improve the layout and consistency of the dashboard.

- **Dashboard UI**:
  - Moved the "View Errors" button into the footer to prevent it from overlapping with other content.
  - Made the page titles consistent across the dashboard by using `<h1>` tags for all pages.
  - Removed unnecessary `padding-bottom` from the `body` element.

## 18. Version 0.8.0 - Remote Control & Centralization

This version marks a major milestone in usability and cluster management by centralizing all configuration and control into the web dashboard.

- **Full Remote Control**:
  - **Node State Management**: Workers now start in a passive `idle` state, waiting for a command from the dashboard.
  - **Start/Stop Buttons**: The dashboard UI was updated with toggleable "Start" and "Stop" buttons for each node, giving administrators full control over when workers are active.
- **Centralized Configuration**:
  - **UI-Driven Settings**: All worker command-line flags (e.g., `--allow-hevc`, `--force-nvidia`, `--min-size`) have been migrated into the "Options" tab of the dashboard.
  - **Database-Driven Workers**: The worker script was refactored to fetch all its settings from the database upon starting a scan. This dramatically simplifies deployment, as the worker now only needs the media directory path to run.
- **Improved Hardware Detection**: The hardware probing logic was made more robust to correctly prioritize NVIDIA GPUs, especially in complex environments like Windows Subsystem for Linux (WSL).
- **Bug Fixes**: Resolved a cascade of bugs related to the new start/stop functionality, ensuring reliable communication between the dashboard and the workers.

## 19. Version 0.8.1 - Granular Control & Advanced Config

This version focused on giving administrators finer control over the transcoding process and individual worker states.

- **Granular Node Control**: The UI was enhanced with individual "Start", "Stop", and "Pause"/"Resume" buttons for each node, providing unambiguous control.
- **Pause/Resume Functionality**: A core feature was added to allow pausing and resuming of transcodes. The worker now handles `SIGSTOP` and `SIGCONT` signals for the underlying `ffmpeg` process, managed via the dashboard.
- **Advanced Configuration in UI**: The "Options" page was expanded to include advanced transcoding settings, moving them from hardcoded values into the database. This includes:
  - Constant Quality (CQ/CRF) values for all encoder types and resolutions.
  - The pixel width threshold for determining HD content.
  - A configurable list of file extensions for the scanner.
- **Debug Flag**: The `--debug` command-line flag was re-introduced to the worker for easy local troubleshooting, allowing it to override the database setting and print the full `ffmpeg` command.

## 20. Version 0.8.4 - The Buggy Release

This release was dedicated to fixing several persistent and complex bugs related to worker state management and UI stability.

- **UI Stability Fix**: Resolved a long-standing issue where the "Start" and "Stop" buttons would incorrectly flip after a worker finished a scan. The worker's state reporting was corrected to ensure the UI remains stable and accurately reflects that the worker is idle.
- **Reliable Quit Command**: Fixed a critical bug where the "Quit" command was unresponsive during an active transcode. The command is now detected within seconds, allowing for an immediate and reliable shutdown of the worker process.
- **Robust Stop Logic**: The "Stop" command was overhauled to ensure the worker finishes its current file and then correctly returns to and stays in its idle state, preventing it from automatically starting another file.

## 21. Version 0.8.5 - State Management & UI Stability

This release focused on fixing a critical and complex UI stability bug related to worker state transitions.

- **Robust State Management**: Introduced a new intermediate `finishing` state for the worker. When a user presses "Stop" during an active transcode, the worker enters this state instead of immediately trying to become idle.
- **UI Stability Fix**: The dashboard UI was updated to recognize the `finishing` state. This resolves a long-standing bug where the "Start" and "Stop" buttons would flip incorrectly. The UI now correctly shows that the worker is busy but will be stopping, and allows the user to press "Start" again to cancel the stop request.

## 22. Version 0.8.6 - History, Stats & Cleanup

This release focused on adding new data management and statistical overview features to the dashboard, while also improving the underlying worker logic.

- **Stats Tab**: A new "Stats" tab was created to provide a high-level overview of the cluster's performance. It includes cards for total files encoded, total original vs. new size (in GB), and the average space reduction percentage.
- **Stale File Cleanup**: A "Cleanup" tab was added to the UI. This feature allows an administrator to scan the media directory for stale temporary (`.tmp_`) and lock (`.lock`) files left behind by crashed workers and delete them safely through the dashboard.
- **Advanced History Management**:
  - The History tab now correctly displays an "In Progress" status for files that are currently being transcoded.
  - A "Clear All History" button was added to allow for easy database maintenance.
  - Users can now delete individual entries from the history log.
- **Dynamic UI**: The "Stats" and "History" tabs were made dynamic, automatically refreshing their content every 5 seconds when they are the active tab.
- **Modernized Worker Logging**: The worker script was updated to no longer use redundant `encoded.list` files, relying entirely on the central database for tracking encode history.