# Architectural Overview

## Introduction
CineBridge Pro is designed as a modular PyQt6 application. The core philosophy is to separate the **UI (View)** from the **Business Logic (Controllers/Workers)** and the **Data/Configuration (Model)**.

## Entry Point
- **`src/cinebridge.py`**: This is the main entry point.
    - Initializes the `QApplication`.
    - Sets up the main `QMainWindow`.
    - Loads global configuration (`QSettings`).
    - Instantiates the main tabs and widgets.
    - Starts global background services (like `SystemMonitor`).

## Module Structure (`src/modules/`)

The application logic is refactored into specialized modules to improve maintainability:

1.  **`config.py`**: 
    - Handles global constants (`DEBUG_MODE`).
    - logging configuration.
    - `AppConfig` helper for centralized settings management.

2.  **`tabs/`**: 
    - Contains granular UI "Screens" of the application (`ingest.py`, `convert.py`, `delivery.py`, `watch.py`, `reports.py`).
    - Each module assembly its respective tab logic and connects it to `Workers`.

3.  **`workers/`**: 
    - Contains all `QThread` subclasses for background processing.
    - **Critical for GUI responsiveness.** Any heavy lifting (file copying, scanning, transcoding) happens here.
    - **`ingest.py`**: `CopyWorker` - Handles Offloading (Copy + Verify + Storage Safety).
    - **`transcode.py`**: `AsyncTranscoder` & `BatchTranscodeWorker`.
    - **`scan.py`**: `ScanWorker`, `ThumbnailWorker`, `IngestScanner`.
    - **`system.py`**: `SystemMonitor`.

4.  **`ui/`**: 
    - Reusable UI components and styling.
    - **`widgets.py`**: `TranscodeSettingsWidget`, `FileDropLineEdit`.
    - **`dialogs.py`**: Standardized popups (Settings, About, MediaInfo, etc.).
    - **`styles.py`**: `ThemeManager` for centralized Dark/Light mode management.

5.  **`utils/`**: 
    - Core business logic libraries (`engine.py`, `registry.py`, `reports.py`, `notifier.py`, `presets.py`).# ...
## Data Flow

1.  **Ingest Flow**:
    - User selects source -> `DeviceRegistry` identifies it.
    - `ScanWorker` finds files.
    - `CopyWorker` copies files -> Emits `file_ready_signal`.
    - If Transcode is enabled, `IngestTab` catches `file_ready_signal` -> Adds job to `AsyncTranscoder` queue.
    - On completion, `ReportGenerator` creates PDF/MHL deliverables based on the user's selected **Destination Strategy** (Project, Global, or Custom).

2.  **Transcode Flow**:
# ...
- **FFmpeg**: The core engine for all media processing. The app looks for it in:
    1. Custom path (Settings).
    2. Bundled PyInstaller `_MEIPASS`.
    3. `src/bin/` (Local dev).
    4. System `PATH`.

- **QtMultimedia**: Used for the native video preview player. On Linux systems, this typically requires the `gstreamer` backend and the `python3-pyqt6.qtmultimedia` package.

- **canberra-gtk-play**: (Linux) Used for playing standardized system notification sounds.
