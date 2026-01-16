# CineBridge Pro: The Professional Linux DIT Suite

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20Windows%20%7C%20macOS-lightgrey.svg)]()

> **The Missing Link for Linux Post-Production.**  
> CineBridge Pro solves the "Resolve on Linux" problem by bridging the gap between professional camera acquisitions and the free version of DaVinci Resolve on Linux.

<p align="center">
  <img src="assets/screen_ingest_clean.png" width="800" alt="CineBridge Pro Main Ingest">
</p>

---

## 🖼️ Interface Gallery

### Ingest & Selection
| Simple Ingest (Default) | Pro DIT Dashboard |
| :---: | :---: |
| ![Simple Ingest](assets/screen_ingest_clean.png) | ![Pro Ingest](assets/screen_ingest_pro.png) |

### Monitoring & Preview
| Instant Video Preview | Settings |
| :---: | :---: |
| ![Preview](assets/screen_preview.png) | ![Settings](assets/screen_settings.png) |

### Advanced Configuration
| Pro Feature Management |
| :---: |
| ![Advanced](assets/screen_advancedfeatures.png) |

---

## 🐧 The Problem & The Solution

**The Gap:** While DaVinci Resolve is a world-class NLE, the **Free Version on Linux** lacks native support for H.264/H.265 (HEVC) codecs due to licensing restrictions. This leaves users with "Media Offline" errors or complex CLI workarounds.

**The Bridge:** CineBridge Pro provides a GUI-driven, professional workflow to:
1.  **Offload** media securely from cameras with checksum verification.
2.  **Transcode** footage into Linux-friendly edit-ready formats (**DNxHR** / **ProRes**).
3.  **Automate** organization and generating DIT reports.

---

## ⚡ Quick Features

| 📥 Professional Ingest | 🛠️ Transcoding & Dailies | 🛡️ Integrity & Safety |
| :--- | :--- | :--- |
| **Multi-Dest Offload:** Backup to 3 drives at once. (Optional) | **Edit-Ready Codecs:** DNxHR HQ/LB & ProRes. | **xxHash64 Verify:** Zero-overhead checksums. |
| **Device Registry:** Auto-detects Sony, BMD, DJI, etc. | **Visual Burn-in:** Timecode, Name, Watermark. | **Visual Reports:** PDF reports with thumbnails. |
| **Smart Filtering:** Video, Photo, Audio filters. | **3D LUTs:** Apply looks during transcode. | **MHL Support:** Industry-standard hash lists. |
| **Video Preview:** Instant scrubbable playback. | **Hardware Accel:** NVENC, QSV, VAAPI support. | **Drive Safety:** Intelligent space pre-check. |

---

## 🚀 Getting Started

### 1. Installation
* **[Download Latest Release](https://github.com/DGxInfinitY/CineBridge-Pro/releases/latest)** (Linux AppImage / Windows Installer)
* Or run from source:
  ```bash
  git clone https://github.com/DGxInfinitY/CineBridge-Pro.git
  pip install PyQt6 psutil xxhash
  python3 src/cinebridge.py
  ```

### 2. Workflow
1.  **Scan:** Select your camera card. CineBridge automatically identifies the device and folder structure.
2.  **Select:** Use the tree view to choose clips. Filter by "Video Only" or specific days.
3.  **Process:** Click **START TRANSFER**.
    *   Files are copied and verified (xxHash64).
    *   (Optional) Proxies are generated in the background.
    *   (Optional) A PDF report or MHL can also be saved alongside media or to a specific destination.

---

## ⚠️ Experimental Support & Multi-Platform Status

**Primary Platform:** Ubuntu Linux (Tested & Verified)

CineBridge Pro is primarily developed and tested on **Ubuntu Linux**. While we provide automated builds for other platforms to increase accessibility, please note the current status:

*   **Linux (.deb / Portable):** High stability. This is the lead development target.
*   **Linux (.rpm / .snap):** **Experimental.** These formats are automatically generated but not manually verified on every release.
*   **Windows (.exe):** **Experimental.** Basic functionality is tested, but UI scaling or hardware acceleration may vary.
*   **macOS (.dmg):** **Experimental.** macOS security restrictions (Gatekeeper) may require manual override to run.

> **Note:** If you encounter issues on non-Ubuntu platforms, please [open an issue](https://github.com/DGxInfinitY/CineBridge-Pro/issues) with details about your environment.

---

## 📦 Detailed Capabilities

### 📥 Professional Ingest
* **Device Registry:** Intelligent, high-reliability auto-detection for Sony (Alpha/FX), Blackmagic (BRAW), Canon (CRM), DJI (Neo 2), GoPro, Insta360, and Android devices.
* **Scan & Select:** A powerful preview phase allowing you to scan your media and select exactly which shoot days or specific clips to transfer.
* **Video Preview:** Double-click any file in the Ingest list to instantly preview it in an integrated, high-performance player.
* **Multi-Destination (Pro):** Simultaneously offload media to up to 3 destinations (e.g., RAID, Shuttle, and Cloud) in a single high-speed pass.
* **Smart Filtering:** Automatically excludes system files and only targets media extensions relevant to your specific camera profile.
* **Standardized Organization:** Automatically sorts files by Date -> Camera -> Category (Video/Photo/Audio/Misc).

### 🛠️ Transcoding & Dailies
* **Edit-Ready Workflows:** Single-click conversion to Linux-friendly codecs (**DNxHR HQ/LB** and **ProRes 422/Proxy**).
* **Visual Overlays (Burn-in):** Professional "Dailies" tools to burn Filenames, Timecodes, and custom Watermarks into your proxies.
* **3D LUT Support:** Apply `.cube` LUTs during transcoding to see your creative intent immediately.
* **Hardware Acceleration:** Native support for NVIDIA (NVENC), Intel (QSV), and AMD/Linux (VAAPI) across all platforms.
* **System Dashboard:** Live monitoring of CPU/GPU load and temperature directly within the transcode interface.

### 🛡️ Data Integrity & Reporting
* **Zero-Overhead Checksums:** High-speed verification that runs concurrently with the copy stream, eliminating the need for a second read pass.
* **Visual Transfer Reports:** Automatically generates professional PDF reports with embedded video thumbnails for every clip.
* **MHL Support:** Generates ASC-MHL compliant XML checksum lists to ensure bit-for-bit accuracy throughout the pipeline.
* **Flexible Storage:** Choose to save reports in the project folder, a fixed global archive, or a custom location per job.

---

## 🎬 Creator-First, DIT-Ready

CineBridge Pro is designed to be **simple by default**. For Creators, YouTubers, and Editors, the out-of-the-box experience provides a clean, 3-step workflow to offload and prep footage without distraction.

### Advanced / DIT Features (Optional)
For professional Digital Imaging Technicians (DITs) or complex workflows, powerful tools can be enabled via the **Settings Menu**:

*   **Watch Folder Service:** Automatically transcode any file dropped into a monitored directory (e.g., from network transfers).
*   **Multi-Destination Ingest:** Offload to 3 drives simultaneously (Primary, Backup, Shuttle) with a single read pass.
*   **Burn-in Overlays:** Apply Timecode, Filename, and Watermarks to dailies for review.
*   **MHL & PDF Reports:** Generate industry-standard hash lists and visual transfer logs for insurance and hand-offs.

> **Note:** These features are disabled by default to keep the interface clean. Enable them in **Settings -> Advanced Features**.

---

## 📝 Change Log

### v4.16.6 (Current Release)
* **Feature:** **Custom Folder Structure.** New template system allows users to define exact output paths (e.g., `{Date}/{Camera}`) or flatten the hierarchy completely.
* **Feature:** **Multi-Select Filter.** Replaced simple "Video Only" toggle with a powerful filter dropdown to select any combination of Video, Photo, and Audio files.
* **Feature:** **Reports Tab.** Dedicated gallery to view and manage past PDF transfer logs (visible when Reports are enabled).
* **UI/UX:** **Creator-First Mode.** Simplified default interface with advanced features (Watch Folder, Reports) hidden until enabled.
* **Stability:** **Resizing Fix.** Resolved layout issues where the window would not shrink after disabling pro features.
* **Refinement:** **Structure Configuration.** New dedicated dialog for managing path templates with live preview.

### v4.16.5
* **Architecture:** Complete modular refactor of the codebase for improved maintainability and long-term stability.
* **UI/UX:** Unified "1-2-3" numbered workflow across all tabs for a professional, consistent experience.
* **Feature:** **Live Transcode Metrics.** Dedicated real-time dashboard for FPS and Encoding Speed (🎬 48 fps | 3.2x Speed).
* **Feature:** **Multi-Destination Ingest.** Offload to up to 3 drives simultaneously with a single read pass.
* **Feature:** **Visual PDF Reports.** Reworked reporting engine to embed frame-accurate thumbnails into PDF hand-offs.
* **Stability:** **Drive-Aware Storage Safety.** Intelligent pre-flight checks that group destinations by physical drive and estimate transcode overhead to prevent disk exhaustion.
* **System:** Expanded **Hardware Monitoring** to track CPU/GPU Load and Temperature for NVIDIA, AMD, and Intel.
* **UX:** Re-organized settings with a new **Advanced Features Dialog** to keep the main interface clean.
* **Refinement:** Intelligent **Camera Profile** selection with auto-sync from detection logic.
* **Refinement:** Reworked **System Notifications** with platform-native sounds and icons.

### v4.16.4
* **New Feature:** **Video Preview.** Instant, scrubbable playback popup for source media in the Ingest tab. (Double-click to view).
* **Performance:** **Zero-Overhead Checksums.** Optimized ingest verification to run concurrently with the copy stream, doubling verification speed.
* **UX:** **Clear Logs.** Added button to clear the Ingest status logs.
* **Improvement:** **DJI Support.** Added detection for newer DJI devices (Neo 2, etc).
* **Fix:** **Smart Transcode.** Resolved issue where 'ProRes' files were not being correctly identified for smart skipping.
* **Fix:** **Linux Compatibility.** Resolved GLib/GStreamer lifecycle conflicts in the video player.

### v4.16.3
* **Architecture:** Complete modular refactor of the codebase (`src/modules/`) for improved maintainability and stability.
* **New Feature:** **Smart Transcode.** Automatically skips re-encoding for source files that are already edit-friendly (DNxHR/ProRes).
* **Stability:** **Watch Folder Safety.** Implemented a "File Stability Check" to prevent transcoding files that are still being copied.
* **Improvement:** **Device Detection.** Fixed false positives where generic USB drives were identified as Blackmagic or Insta360 cameras.
* **UI/UX:** Enhanced dark mode support for Job Reports and improved responsiveness during large media scans.
* **Dev:** Added automated unit test suite.

### v4.16.1
* **UI/UX:** Added "Experimental / Pro Features" section in Settings to toggle the visibility of **Watch Folder** and **Burn-in Tools**.
* **Improvement:** Optimized system resources by consolidating background monitors into a single global instance.
* **Stability:** Hardened application shutdown logic to prevent hangs during heavy background processing.

### v4.16.0
* **New Feature:** **Watch Folder Service.** Background proxy generation for any files dropped into a watched directory.
* **New Feature:** **Professional Burn-In.** Added Timecode, Filename, and Watermark overlays for Dailies.
* **New Feature:** **DIT PDF Reports.** Beautiful project hand-off documents generated automatically.
* **New Feature:** **MHL Support.** Industry-standard XML checksum lists for media integrity.

### v4.15.x
* **Refactor:** Standardized data storage using **XDG XDG Base Directory** specs (`~/.local/share/cinebridge-pro`).
* **New Feature:** **Transcode Preset Management.** Full suite to Save, Import, and Export custom profiles.
* **Distribution:** Added a professional Windows Setup Installer and automated metadata synchronization.

### v4.14.0
* **New Feature:** **Ingest Overhaul.** High-performance "Scan Source" phase with Tree View selection.
* **New Feature:** **Metadata Viewer.** Right-click queue items to inspect codec, resolution, and bitrate.
* **New Feature:** **Visual Thumbnails.** Added high-quality frame extraction for the job queue.
* **Design:** Completely updated UI with a responsive Dashboard layout and new modern "Bridge" icon.

---

## ⚙️ Configuration & Debugging
* **FFmpeg Settings:** Manually select custom FFmpeg binaries to unlock specialized hardware features.
* **Troubleshooting:** Detailed, structured logs are saved to `~/cinebridge_pro.log` (accessible via the Settings menu).

---

Developed by **Donovan Goodwin** with help from Gemini AI.
