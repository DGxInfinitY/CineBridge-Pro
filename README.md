# CineBridge Pro: The Linux DIT Suite

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20Windows%20%7C%20macOS-lightgrey.svg)]()

**CineBridge Pro** is an open-source Digital Imaging Technician (DIT) tool designed to solve the "Resolve on Linux" problem. It handles secure media offloading, checksum verification, and edit-ready transcoding (DNxHR/ProRes) in a single, streamlined interface.

![CineBridge Pro Screenshot](assets/screenshot.png)

---

## 🚀 Key Features

### 📥 Intelligent Ingest
* **Auto-Detection (Registry):** High-reliability detection for Sony (Alpha/FX), Blackmagic (BRAW), Canon (CRM), DJI, GoPro, Insta360, and Android.
* **Ingest Preview:** Scan your source and select exactly which days or files to transfer before starting.
* **Smart Filtering:** Automatically filters file extensions based on the detected camera profile.
* **Checksum Verification:** Bit-for-bit verification using **xxHash64** (fastest) or MD5 (compatibility).
* **Pre-Flight Storage Check:** Prevents ingest if the destination drive lacks sufficient space.

### 🛠️ Transcoding Engine
* **Edit-Ready Codecs:** Converts H.264/H.265/BRAW into **DNxHR** or **ProRes** for smooth editing in DaVinci Resolve.
* **3D LUT Burn-in:** Apply .cube LUTs during transcode for instant dailies.
* **Audio Drift Fix:** Automatically synchronizes variable frame rate audio and normalizes to 48kHz.
* **Hardware Acceleration:** Full support for NVIDIA (NVENC), Intel (QSV), VAAPI, and MacOS VideoToolbox.
* **Batch Mode:** Drag-and-drop interface with **Visual Thumbnails** for bulk converting footage.

### 🛡️ Safety & Reliability
* **Metadata Viewer:** Right-click any file in the queue to inspect codec, bitrate, and resolution.
* **Configurable FFmpeg:** Easily select custom FFmpeg binaries to unlock specialized hardware features.
* **Detailed Debugging:** Structured logging saved to `~/cinebridge_pro.log` for professional troubleshooting.
* **Theme Aware:** Automatically syncs with system Dark/Light mode.

---

## 📦 Installation

### 📥 Releases (Pre-Compiled)
Download the standalone executable for your OS.

* **[Download Latest Release Here](https://github.com/DGxInfinitY/CineBridge-Pro/releases/latest)**

### 🛠️ Manual Build (For Developers)

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/DGxInfinitY/CineBridge-Pro.git
    cd CineBridge-Pro
    ```

2.  **Install Dependencies:**
    ```bash
    pip install PyQt6 psutil xxhash
    ```

3.  **Run the App:**
    ```bash
    python3 src/cinebridge.py
    ```

### 📋 Prerequisites
* **Python 3.10+** (If running from source)
* **FFmpeg** (Included in releases, or install on system)
    * **Linux:** `sudo apt install ffmpeg`
    * **Mac:** `brew install ffmpeg`

---

## 📝 Change Log

### v4.14.0 (Current Release)
* **New Feature:** **Ingest Overhaul.** Added a "Scan Source" phase allowing users to select specific dates/files via a Tree View before transfer.
* **New Feature:** **Device Registry.** Professional fingerprinting for Sony, BMD, Canon, GoPro, DJI, and Insta360.
* **New Feature:** **3D LUT Support.** Users can now select a `.cube` file to burn into transcoded footage.
* **New Feature:** **Metadata Viewer.** Added "Inspect Media Info" context menu to the job queue.
* **New Feature:** **Visual Queue.** Added high-quality thumbnails to the Batch Conversion queue.
* **New Feature:** **FFmpeg Configuration Center.** Fully overhauled FFmpeg settings with custom binary selection and hardware strategy display.
* **Improvement:** Added **Audio Drift Fix** toggle to solve audio sync issues in DaVinci Resolve.
* **Improvement:** Implemented structured logging to `~/cinebridge_pro.log` for better support.
* **UX:** New "Dashboard" layout for Ingest Tab to better utilize widescreen real estate.
* **Design:** Updated App Icon to new modern "Bridge" design.

---

### v4.13.5
* **New Feature:** Added Native OS Notifications and sound alerts.
* **New Feature:** Added "Verify Copy" toggle using xxHash64.
* **New Feature:** Added Pre-Flight Storage Check.