# Component Map

This document maps the source files to their primary responsibilities and contained classes.

## `src/cinebridge.py`
**Role:** Application Bootstrapper & Main Window
- `CineBridgeApp(QMainWindow)`: The root window. Manages the top-level TabWidget and global signals.

## `src/modules/config.py`
**Role:** Configuration & Logging
- `AppConfig`: Static methods for reading/writing global config state.
- `AppLogger`: Sets up file-based logging (`cinebridge_pro.log`).

## `src/modules/tabs.py`
**Role:** Main UI Screens (Tabs)
- `IngestTab(QWidget)`: The "Ingest" tab. Handles drive scanning, file selection, and copy operations.
- `ConvertTab(QWidget)`: The "Convert" tab. Drag-and-drop transcoding interface.
- `DeliveryTab(QWidget)`: The "Delivery" tab. Similar to Convert but tailored for web/delivery codecs.
- `WatchTab(QWidget)`: The "Watch Folder" tab. Manages the automated background monitoring service.

## `src/modules/workers.py`
**Role:** Background Threads (Concurrency)
- `ScanWorker`: Scans system mount points for drives.
- `ThumbnailWorker`: Generates thumbnail images for video files using FFmpeg.
- `IngestScanner`: Recursively scans a source folder for media files.
- `AsyncTranscoder`: Queue-based transcoder. Processes jobs one by one to avoid system overload.
- `CopyWorker`: The heavy lifter for Offloading. Handles Copy, Verification (xxHash/MD5), and Reporting.
- `BatchTranscodeWorker`: Used by Convert/Delivery tabs for simple list-based processing.
- `SystemMonitor`: Polls CPU usage for the UI dashboard.

## `src/modules/widgets.py`
**Role:** Reusable UI Components
- `TranscodeSettingsWidget`: The "Settings" panel inside Convert/Ingest tabs.
- `FileDropLineEdit`: A text input that accepts file drags.
- `SettingsDialog`: The main application preferences window.
- `MediaInfoDialog`: Popup showing codec details (using `ffprobe`).
- `FFmpegConfigDialog`: Settings for managing the FFmpeg binary path.

## `src/modules/utils.py`
**Role:** Business Logic & Libraries
- `DeviceRegistry`: Definitions for Camera Folder structures (Sony, Canon, BMD, etc.).
- `DriveDetector`: OS-specific logic to find mounted volumes (Linux/Win/Mac).
- `TranscodeEngine`: Generates FFmpeg CLI commands.
- `DependencyManager`: Locates external binaries (ffmpeg, ffprobe).
- `ReportGenerator`: Generates PDF reports.
- `MHLGenerator`: Generates ASC-MHL XML checksum lists.
- `PresetManager`: Saves/Loads JSON transcoding presets.
