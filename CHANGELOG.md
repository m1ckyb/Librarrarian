# [Unreleased]

### Added

## [0.8.7] - 2025-11-21 - UI Refinements & Bug Fixes

### Added
- **Node Health Indicator**: Added a colored dot (green/orange/red) next to each worker's hostname to provide an at-a-glance view of its health based on the last heartbeat.
- **Search & Pagination**: Implemented search and pagination for the history table, making it easier to navigate large numbers of encoded files.

### Changed
- **Consolidated UI**: Merged the "History" and "Stats" tabs into a single "History & Stats" tab to simplify the interface.
- **UI Polish**:
  - The "View Errors" button is now consistently styled and only turns red when errors are present, otherwise remaining in its default outline style.
  - The footer now has a more pronounced "glass" effect with increased transparency.

### Fixed
- **Layout & Stability**: Fixed numerous UI bugs, including:
  - A floating pagination bar on the history tab.
  - Inconsistent button colors between tabs.
  - JavaScript errors that broke UI components like the node control buttons.
  - A typo in the footer HTML (`/span>`).

## [0.8.6] - 2025-11-20 - History, Stats & Cleanup

### Added
- **Stats Tab**: A new tab was added to the dashboard to display aggregate statistics, including total files encoded, total original vs. new size, and average space reduction.
- **Stale File Cleanup**: A new "Cleanup" tab was added to find and delete stale `.lock` and `.tmp_` files left behind by crashed workers.
- **Advanced History Management**:
  - The History tab now shows "In Progress" for files currently being encoded.
  - Added a "Clear All History" button to truncate the history table.
  - Added the ability to delete individual entries from the history log.
- **Dynamic Tabs**: The "Stats" and "History" tabs now automatically refresh their content every 5 seconds when active.

### Changed
- **Redundant File Removal**: The worker no longer writes to local `encoded.list` files, relying solely on the database for history tracking.
- **History Logging**: The worker now logs a file to the history table with an `encoding` status when it starts a job, and updates it to `completed` upon success.

## [0.8.5] - 2025-11-20 - State Management & UI Stability

### Fixed
- **UI Stability**: Resolved a long-standing bug where the "Start" and "Stop" buttons would flip incorrectly. When "Stop" is pressed during a transcode, the worker now enters an intermediate `finishing` state. This allows the UI to correctly reflect the worker's intent to stop, enabling the "Start" button to cancel the stop request.

### Bugs
- **Quit Command Reliability**: The "Quit" command is not always responsive and can be ignored if a worker is in the middle of a long transcode process.

## [0.8.1] - 2025-11-20 - Granular Control & Advanced Config

### Added
- **Granular Node Control**: Replaced the single toggle button with individual "Start", "Stop", and "Pause"/"Resume" buttons for clearer and more precise control over each worker.
- **Pause/Resume Functionality**: Implemented the ability to pause a transcode in progress and resume it later. The worker sends the appropriate signals (`SIGSTOP`/`SIGCONT`) to the `ffmpeg` process.
- **Advanced Transcoding Configuration**: Exposed core transcoding parameters in the "Options" tab of the UI, allowing for dynamic configuration of:
  - Constant Quality (CQ/CRF) values for each encoder type (NVIDIA, VAAPI, CPU) and resolution (HD/SD).
  - The pixel width threshold that defines a video as "HD".
  - The list of scannable file extensions.
- **Debug Flag**: Re-introduced the `--debug` command-line flag for the worker script. When used, it overrides the database setting and prints the full `ffmpeg` command to the console for easier troubleshooting.

### Changed
- The worker's main loop was refactored to fetch and use the new advanced transcoding settings from the database.

## [0.8.0] - 2025-11-20 - Remote Control & Centralization

### Added
- **Full Remote Control**: Added toggleable "Start" and "Stop" buttons for each node on the dashboard, allowing for complete remote management of the cluster's state.
- **Centralized Configuration**: All worker command-line arguments (e.g., `--allow-hevc`, `--force-nvidia`) are now configurable via the "Options" tab in the dashboard.

### Changed
- **Worker Logic**: Workers now start in an `idle` state and wait for a "Start" command from the dashboard before beginning to process files.
- **Database-Driven Workers**: The worker script (`transcode.py`) has been refactored to fetch all its configuration from the database. It now only requires the media directory as a command-line argument, simplifying deployment.
- **Hardware Detection**: The hardware probing logic was significantly improved to be more reliable, especially for detecting NVIDIA GPUs on systems running Docker or Windows Subsystem for Linux (WSL).

### Fixed
- **Start Command**: Resolved a series of bugs that prevented the "Start" command from working correctly, including database column name mismatches and frontend/backend communication errors.

## [0.7.4] - 2025-11-20 - CSS Loading Fix

### Fixed
- **CSS Loading Order**: Moved the Bootstrap CSS link to the `base.html` template to ensure it loads before custom styles that depend on it. This fixed two resulting bugs:
  - The footer in dark mode now has the correct background color.
  - The badge on the "View Errors" button has the correct text contrast on all button colors.

## [0.7.3] - 2025-11-20 - UI Refinements

### Changed
- **Dashboard UI**: Merged the `/options` page into a new "Options" tab on the main dashboard to consolidate all controls in one place.
- **Dashboard Layout**: Refined the header layout by moving the "View Errors" button inline with the page title and placing the "Updated" clock on its own line for better alignment.

### Fixed
- **UI Visibility**: Improved the text contrast of the badge on the "View Errors" button to ensure it is readable against all background colors (e.g., green or red).
- **Dark Mode Footer**: The footer in dark mode is now darker, providing better visual separation from the page content.

## [0.7.2] - 2025-11-20 - CSS Fixes

### Fixed
- **Dashboard UI**: Fixed several CSS issues to improve the layout and consistency of the dashboard.
  - Moved the "View Errors" button into the footer to prevent it from overlapping with other content.
  - Made the page titles consistent across the dashboard by using `<h1>` tags for all pages.
  - Removed unnecessary `padding-bottom` from the `body` element.

## [0.7.1] - 2025-11-19 - The Non-Interactive Fix

### Changed
- **Worker Self-Update**: The self-update mechanism is now non-interactive to prevent terminal-related bugs within Docker. An `--update` command-line flag was added to enable this, and it is now the default for the Docker Compose service.

### Fixed
- **Update Prompt Bug**: Fixed a bug where the interactive update prompt would not accept input inside a Docker container due to line ending issues (`^M`).

## [0.7.0] - 2025-11-19 - The Boring & Broken Update

### Fixed
- **Worker Rescan Delay**: Corrected a critical bug where the worker would ignore the user-defined rescan delay and default to a 60-second wait. The delay now works as intended.
- **Dashboard Layouts**: Fixed numerous UI layout and rendering bugs across the dashboard.
  - Corrected the active node card display, which was broken due to a copy-paste error.
  - Moved the "Updated" timestamp and theme switcher to the footer to create a consistent header and prevent layout shifting on all pages.
- **Worker Self-Update**: The worker's self-update check now correctly points to the `develop` branch, resolving "404 Not Found" errors.
- **Dashboard Stability**: Added a `secret_key` to the Flask application, resolving crashes related to session management when saving options.
- **Dashboard Robustness**: The options page is now resilient and will no longer crash if the worker has not yet populated the settings in the database.

## [0.6.0] - 2025-11-19 - Command & Control

### Added
- **Worker Options Page**: Created a new `/options` page in the dashboard to allow for dynamic configuration of worker behavior.
- **Database-Driven Settings**: Implemented a new `worker_settings` table in the database to store and persist configuration, with sensible defaults.
- **Configurable Rescan Delay**: Added an option with a slider (0-60 minutes) to set a delay before workers rescan for files after a successful batch.
- **Configurable Folder Exclusion**: Added an option to make workers completely ignore directories named `encoded`.

### Changed
- **Worker Logic**: The worker now fetches the latest settings from the database at the start of every scan cycle and applies them.

## [0.5.0] - 2025-11-19 - Into the Darkness

### Added
- **UI Theme Switcher**: Implemented a full-featured theme switcher in the dashboard with support for Light, Dark, and System-default modes. The user's preference is saved in local storage.

### Changed
- **Footer Layout**: The dashboard footer was redesigned with a split layout, placing the version on the left and the project link on the right.
- **Template Inheritance**: Refactored the dashboard's frontend by creating a `base.html` template to centralize the page structure, theme logic, and footer, simplifying `index.html`.


## [0.4.2] - 2025-11-19

### Changed
- **Worker Versioning**: The worker script will now fall back to a version identifier of `"standalone"` if the `VERSION.txt` file is not found, preventing crashes when run outside of the main project structure.

### Fixed
- **Dashboard UI**: Added padding to the bottom of the dashboard page to prevent the fixed footer from overlapping the "View Errors" button.

## [0.4.1] - 2025-11-19

### Added
- **Centralized Versioning**: Created a single `VERSION.txt` file at the project root to act as the single source of truth for versioning across all components.
- **UI Polish**: The dashboard footer is now fixed to the bottom of the page with a semi-transparent "glassy" effect.
- **Conditional UI**: The "Clear Errors" button on the dashboard is now hidden if there are no errors to clear.


## [0.4.0] - 2025-11-19

### Added
- **FPS Display**: The dashboard now shows the Frames Per Second (FPS) for each active transcoding node.
- **Dynamic Error Button**: The "View Errors" button is now green when there are no errors and red if errors are present.
- **Local Timestamp**: The "Updated" timestamp now reflects the user's local browser time.
- **Application Footer**: Added a footer to the dashboard containing the web UI version and a link to the project's GitHub repository.