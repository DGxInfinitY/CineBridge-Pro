# CineBridge Pro: Project Memory

## 🚀 Development Cycle
We follow a strict incremental development workflow:
1.  **Incremental Work:** All features and fixes are developed on the `dev` branch.
2.  **Live Updates:** Every code change is automatically pushed to `origin dev` to maintain transparency for online followers.
3.  **Release Process:**
    *   Merge `dev` into `master`.
    *   Tag the release on `master` (e.g., `v4.16.4`).
    *   Trigger the build system for production binaries.
4.  **Post-Release:**
    *   Immediately switch back to `dev`.
    *   Bump the version string to the next increment with a suffix (e.g., `v4.16.5 (Dev)`).
    *   Continue development.

## 🎨 UI & UX Standards
*   **Logical Flow:** Use explicit "1-2-3" numbering for workflow steps in every tab.
*   **Top Alignment:** Always use vertical stretches (`addStretch()`) to keep settings and forms biased to the top of GroupBoxes, preventing "floaty" behavior during resize.
*   **Unified Feedback:** Use the "DashFrame" container for status labels and progress bars at the bottom of every tab.
*   **Context-Aware Popups:** Completion dialogs and system notifications must be specific to the task performed (e.g., "Ingest Successful" vs "Render Complete").
*   **Tooltips:** Maintain descriptive tooltips for every interactive element to aid user onboarding.

## 🛠️ Technical Knowledge
*   **Multimedia (Ubuntu):** Install via `sudo apt install python3-pyqt6.qtmultimedia`.
*   **FFmpeg:** Maintain a "Hardware First" strategy (NVENC > QSV > VAAPI > CPU). Use caching for hardware detection to ensure snappy UI responsiveness.
*   **System Monitoring:** Multi-vendor support for NVIDIA, AMD, and Intel GPUs across Linux and Windows. Use `nvidia-smi` where available, and `sysfs` (Linux) or `PowerShell` (Windows) as fallbacks.
*   **Video Preview:** Use a **Persistent Dialog Strategy**. Maintain one dialog instance and reset the video output surface on each load to ensure fast, stable playback on Linux.