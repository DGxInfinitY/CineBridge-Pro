# Component Map

This document maps the source files to their primary responsibilities and contained classes.

## `src/cinebridge.py`
**Role:** Application Bootstrapper & Main Window
- `CineBridgeApp(QMainWindow)`: The root window. Manages the top-level TabWidget and global signals.

## `src/modules/config.py`
**Role:** Configuration & Logging
- `AppConfig`: Static methods for reading/writing global config state.
- `AppLogger`: Sets up file-based logging (`cinebridge_pro.log`).

## `src/modules/tabs/`
**Role:** Main UI Screens (Tabs)
- `ingest.py`: `IngestTab(QWidget)` - Drive scanning, file selection, and copy operations.
- `convert.py`: `ConvertTab(QWidget)` - Drag-and-drop transcoding interface.
- `delivery.py`: `DeliveryTab(QWidget)` - Tailored for web/delivery codecs.
- `watch.py`: `WatchTab(QWidget)` - Automated background monitoring service.

## `src/modules/workers/`
**Role:** Background Threads (Concurrency)
- `scan.py`: `ScanWorker`, `ThumbnailWorker`, `IngestScanner`.
- `transcode.py`: `AsyncTranscoder`, `BatchTranscodeWorker`.
- `ingest.py`: `CopyWorker` - Copy, Verification (xxHash/MD5), and Storage Safety.
- `system.py`: `SystemMonitor` - Polls CPU/GPU usage for the UI dashboard.

## `src/modules/ui/`
**Role:** Reusable UI Components & Styling
- `widgets.py`: `TranscodeSettingsWidget`, `FileDropLineEdit`.
- `styles.py`: `ThemeManager` - Centralized application styling and theme detection.
- `dialogs.py`: Standardized popups (Settings, About, MediaInfo, VideoPreview, etc.).

## `src/modules/utils/`
**Role:** Business Logic & Libraries
- `registry.py`: `DeviceRegistry`, `DriveDetector`.
- `engine.py`: `TranscodeEngine`, `MediaInfoExtractor`.
- `reports.py`: `ReportGenerator`, `MHLGenerator`.
- `notifier.py`: `SystemNotifier`.
- `presets.py`: `PresetManager`.
- `common.py`: `EnvUtils`, `DependencyManager`.
