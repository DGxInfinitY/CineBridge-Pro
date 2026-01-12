# CineBridge Pro Project Memory

## Core Mission
To provide a professional, open-source DIT and Post-Production suite for Linux, specifically bridging the H.264/H.265 gap in DaVinci Resolve.

## Development Environment
- **Branch Strategy:** `dev` for active work, `master` for stable releases.
- **OS Focus:** Primary development on Linux (Ubuntu), with robust cross-platform support for Windows and macOS.
- **Testing:** Modular architecture in `tests/` using `unittest`.

## Version Milestones
- **v4.16.4 (Current Master):** Added Video Preview popup, Zero-Overhead checksums, and improved DJI Neo 2 detection.
- **v4.16.5 (In Development):** 
    - **Unified UI:** Implemented standardized "1-2-3"Numbered flows across all tabs.
    - **Pro Features:** Multi-destination simultaneous ingest and Visual PDF Reports (with thumbnails).
    - **Smart Profiles:** Camera Profile dropdown with automatic detection sync.
    - **Hardware Monitor:** Expanded tracking for NVIDIA, AMD, and Intel GPUs across Linux and Windows.
    - **Stability:** Re-engineered System Notifications and context-aware completion dialogs.

## Knowledge & Preferences
- **Dependencies:** On Ubuntu, install multimedia via `sudo apt install python3-pyqt6.qtmultimedia`.
- **UI Logic:** Always keep settings biased to the top of group boxes using vertical stretches.
- **FFmpeg:** Preference for hardware acceleration (NVENC/QSV/VAAPI) where available.
- **Workflow:** Use "1-2-3" numbering for all new tab layouts to maintain a unified user experience.
