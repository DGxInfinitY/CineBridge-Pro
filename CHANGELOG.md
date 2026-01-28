# CineBridge Pro Changelog

## [v4.17.7] - 2026-01-20
### New Features
*   **Robust Device Detection:**
    *   **Linux `lsblk` Integration:** Now prioritizes Volume Labels (e.g., "DJI_OSMO", "Samsung_T7") for identification, making detection immune to folder renaming.
    *   **Advanced GoPro Detection:** Instant identification via `version.txt` and `MISC` files (OpenGoPro logic).
    *   **Advanced DJI Detection:** Scans for unique log files (`fc_log.log`, etc.) and metadata tags to identify drones even if standard folder structures are modified.
*   **Folder Structure Configuration:**
    *   Added **"Edit-Ready Primary"** mode (User Request): Transcoded files are placed at the root (e.g., `Project/Device/Date/Clip_EDIT.mov`), and Source files are safely nested in a `Source/` subfolder.
    *   Added configurable **Source Root** and **Transcode Folder** names.
    *   Default structure updated to **Device Centric** (`{Camera}/{Date}`).
*   **Delivery & Quality Fixes:**
    *   **High-Quality Transcoding:** Switched H.264/H.265 NVENC settings from `fast` to **P4 (Medium/High Quality)** with **Constant QP (CQP)** rate control. This fixes pixelation issues on cards like the GTX 1070 Ti.
    *   **Reliability:** Fixed logic errors causing silent failures in H.264 delivery.
    *   **Debugging:** Added stderr log capture for instant transcode failure feedback.

## [v4.17.6] - 2026-01-19
*   **Dashboard:** Unified Hardware Monitor and Transcode Metrics into a single responsive dashboard row.
*   **Progress Tracking:** Added dual-stage progress tracking (Copy -> Transcode) and granular file counters.
*   **Preview:** Implemented Hybrid Preview (FFmpeg pipe + FFplay) for smoother playback on Linux.
*   **UX:** Added inline device renaming and persistent overrides.

## [v4.17.5] - 2026-01-15
*   **Fix:** Resolved Snapcraft build failures.
*   **Fix:** Fixed crash when ingesting from empty source folders.
