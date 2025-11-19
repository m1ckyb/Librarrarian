# Changelog

All notable changes to this project will be documented in this file.

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