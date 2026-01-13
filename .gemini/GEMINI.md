# CineBridge Pro: Project Memory

## 🚀 Project Overview
**CineBridge Pro** is a high-performance Digital Imaging Technician (DIT) and Post-Production suite for Linux, Windows, and macOS. It bridges the gap between professional camera acquisitions and Linux-based NLEs like DaVinci Resolve by providing secure offloading, verification, and transcoding workflows.

### Current Version: v4.16.5
- **Latest Development:** Modular refactor, Intelligent Storage Safety, and Live Transcode Metrics.
- **Next Milestone:** v4.17.0 refinement cycle.

## 📈 Development Workflow
We follow a strict incremental development cycle:
1.  **Incremental Work:** All features and fixes are developed on the `dev` branch.
2.  **Live Updates:** Every code change is pushed to `origin dev` for transparency.
3.  **Release Process:**
    *   Merge `dev` into `master`.
    *   Tag the release on `master` (e.g., `v4.16.5`).
    *   Bump `dev` to the next increment (e.g., `v4.16.6 (Dev)`).

## 🎨 UI & UX Standards
*   **Logical Flow:** Explicit "1-2-3" numbering for workflow steps in every tab.
*   **Top Alignment:** Use vertical stretches (`addStretch()`) to keep settings biased to the top.
*   **Unified Feedback:** Use the "DashFrame" container for status and progress at the bottom of every tab.
*   **Dashboard Components:** 
    *   Progress Bar (Global for the active task).
    *   **Transcode Metrics:** Real-time FPS and Speed display (🎬 00 fps | 0.0x Speed).
    *   **Hardware Monitor:** CPU/GPU Load and Temperature.
*   **Context-Aware Popups:** Use `JobReportDialog` for task completion.

## 🛠️ Technical Architecture
*   **Modularity:** The codebase is split into granular packages:
    *   `src/modules/tabs/`: Tab-specific UI logic.
    *   `src/modules/workers/`: Multi-threaded background logic (`QThread`).
    *   `src/modules/ui/`: Reusable widgets and `ThemeManager` for centralized styling.
    *   `src/modules/utils/`: Core processing libraries (FFmpeg engine, Registry, Reports).
*   **FFmpeg Strategy:** "Hardware First" (NVENC > QSV > VAAPI > CPU).
*   **Storage Safety:** 
    *   **Drive-Aware Check:** Groups multiple destinations by physical drive/mount point to accurately calculate required space.
    *   **Predictive Estimation:** Accounts for both source file size and estimated transcode overhead before starting.
*   **Video Preview:** **Persistent Dialog Strategy**. Maintains one dialog instance and resets the output surface for stability on Linux.
*   **Data Integrity:** Multi-threaded verification (xxHash64/MD5) integrated into the main copy stream.

## 📋 Dependencies
*   **Core:** Python 3.10+, PyQt6, psutil, xxhash.
*   **Media:** FFmpeg (binary path configurable in settings).
*   **Linux Specifics:** `python3-pyqt6.qtmultimedia` and `canberra-gtk-play`.
