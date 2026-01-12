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

2.  **`tabs.py`**: 
    - Contains the major UI "Screens" of the application (`IngestTab`, `ConvertTab`, `DeliveryTab`, `WatchTab`).
    - Each class here is a `QWidget` that assembles smaller widgets and connects them to `Workers`.

3.  **`workers.py`**: 
    - Contains all `QThread` subclasses for background processing.
    - **Critical for GUI responsiveness.** Any heavy lifting (file copying, scanning, transcoding) happens here.
    - Key Workers:
        - `CopyWorker`: Handles the "Ingest" process (Copy + Verify + Report).
        - `AsyncTranscoder`: A queue-based worker for transcoding jobs.
        - `ScanWorker`: Detects attached drives and camera cards.

4.  **`widgets.py`**: 
    - Reusable UI components.
    - `TranscodeSettingsWidget`: The complex form for selecting codecs/presets.
    - `SettingsDialog`: The global preferences window.
    - `JobReportDialog`: Popup for displaying logs/reports.

5.  **`utils.py`**: 
    - Static helper classes and libraries.
    - `DeviceRegistry`: Logic for identifying camera card structures (Sony vs Blackmagic vs Generic).
    - `TranscodeEngine`: Wrapper around `ffmpeg` command generation.
    - `ReportGenerator` & `MHLGenerator`: Create PDF and XML deliverables.

## Data Flow

1.  **Ingest Flow**:
    - User selects source -> `DeviceRegistry` identifies it.
    - `ScanWorker` finds files.
    - `CopyWorker` copies files -> Emits `file_ready_signal`.
    - If Transcode is enabled, `IngestTab` catches `file_ready_signal` -> Adds job to `AsyncTranscoder` queue.

2.  **Transcode Flow**:
    - `AsyncTranscoder` pops job from queue.
    - Calls `TranscodeEngine.build_command()` to get `ffmpeg` arguments.
    - Executes `ffmpeg` as a subprocess.
    - Parses `stderr` for progress updates -> Emits signals to UI.

## External Dependencies
- **FFmpeg**: The core engine for all media processing. The app looks for it in:
    1. Custom path (Settings).
    2. Bundled PyInstaller `_MEIPASS`.
    3. `src/bin/` (Local dev).
    4. System `PATH`.

- **QtMultimedia**: Used for the native video preview player. On Linux systems, this typically requires the `gstreamer` backend and the `python3-pyqt6.qtmultimedia` package.
