# CodecShift Project Summary

**CodecShift** is a distributed video transcoding cluster designed to automate the conversion of a media library to the efficient HEVC (H.265) codec. It uses a central web dashboard to manage a fleet of worker nodes, making it easy to scale processing power across multiple machines.

## Core Architecture

The system is built on a client-server model:

1.  **Dashboard (The Brain)**: A Flask-based web application that acts as the central controller. It integrates with Plex Media Server to find files, manages a job queue in a PostgreSQL database, and provides a real-time UI for monitoring and configuration.

2.  **Worker (The Muscle)**: A "dumb" but powerful transcoding engine. Workers connect to the dashboard, request a job, perform the transcode using FFmpeg with hardware acceleration (NVIDIA, Intel, Apple), and report the result.

3.  **Database (The Memory)**: A PostgreSQL database that stores the job queue, node status, historical data, and all system settings.

This architecture allows for a robust, scalable, and easy-to-manage transcoding pipeline, all orchestrated with Docker Compose.

## Key Features

*   **Automated Plex Scanning**: Integrates with Plex to automatically find and queue media for transcoding based on user-selected libraries.
*   **Centralized Job Management**: A web dashboard provides a real-time view of the job queue, worker status, and transcoding history.
*   **Distributed Workers**: Scale transcoding capacity by adding more worker nodes, which request jobs from the central dashboard.
*   **Dynamic Configuration**: All settings, from Plex credentials to transcoding quality, are managed through the web UI.
*   **Hardware Acceleration**: Automatically utilizes NVIDIA (NVENC), Intel (QSV), and Apple (VideoToolbox) for fast transcoding.