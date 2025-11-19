# Changelog

All notable changes to this project will be documented in this file.

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