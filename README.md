# CineBridge Pro: The Linux DIT Suite

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20Windows%20%7C%20macOS-lightgrey.svg)]()

**CineBridge Pro** is an open-source Digital Imaging Technician (DIT) tool designed to solve the "Resolve on Linux" problem. It handles secure media offloading, checksum verification, and edit-ready transcoding (DNxHR/ProRes) in a single, streamlined interface.

![CineBridge Pro Screenshot](assets/screenshot.png)

---

## 🚀 Key Features

### 📥 Intelligent Ingest
* **Auto-Detection:** Instantly recognizes GoPros, DJI Drones, Android Phones (MTP), and Professional Cameras.
* **"Sniper Mode":** Targeted scanning for massive MTP devices (like Pixel phones) to avoid hanging on thousands of system files.
* **Checksum Verification:** Bit-for-bit verification using **xxHash64** (fastest) or MD5 (compatibility).
* **Organization:** Automatically sorts footage by Date and Camera Type into a structured folder hierarchy.
* **Pre-Flight Storage Check:** Prevents ingest if the destination drive lacks sufficient space.

### 🛠️ Transcoding Engine
* **Linux-Friendly Codecs:** Converts H.264/H.265 footage into **DNxHR** or **ProRes** for smooth editing in DaVinci Resolve on Linux (Free Version).
* **Hardware Acceleration:** Supports NVIDIA (NVENC), Intel (QSV), and VAAPI for blazing fast encoding.
* **Batch Mode:** Drag-and-drop interface for bulk converting existing footage.

### 🛡️ Safety & Reliability
* **Native Notifications:** System alerts (Toast/Notify) and sounds when long jobs finish.
* **Logging:** Detailed logs for every file copied and every frame transcoded.
* **Theme Aware:** Automatically syncs with your system's Dark/Light mode preferences.

---

## 📦 Installation

### 📥 Releases (Pre-Compiled)
Don't want to touch code? Download the standalone executable for your OS.

* **[Download Latest Release (Linux AppImage / Windows .exe)](https://github.com/DGxInfinitY/CineBridge-Pro/releases/latest)**

### 🛠️ Manual Build (For Developers)

#### Option A: Run from Source
Best for testing changes or debugging.

1.  **Clone the Repository:**
    ```bash
    git clone [https://github.com/DGxInfinitY/CineBridge-Pro.git](https://github.com/DGxInfinitY/CineBridge-Pro.git)
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

#### Option B: Build Standalone Executable
Create a portable binary (single file) to share with others.

1.  **Install PyInstaller:**
    ```bash
    pip install pyinstaller
    ```

2.  **Build the Binary:**
    * **Linux/macOS:**
        ```bash
        pyinstaller --noconfirm --onefile --windowed --name "CineBridgePro" --add-data "assets:assets" src/cinebridge.py
        ```
    * **Windows:**
        ```powershell
        pyinstaller --noconfirm --onefile --windowed --name "CineBridgePro" --add-data "assets;assets" src/cinebridge.py
        ```

3.  **Locate the File:**
    The finished executable will be in the `dist/` folder.

### 📋 Prerequisites
* **Python 3.10+** (If running from source)
* **FFmpeg** (Must be installed and on your system PATH)
    * **Linux:** `sudo apt install ffmpeg`
    * **Mac:** `brew install ffmpeg`
    * **Windows:** Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add `bin` folder to PATH.

---

## ⚙️ Configuration

Click the **Gear Icon (⚙)** in the top right to access the Control Panel:
* **Theme:** Toggle between Light, Dark, or Auto (System Sync).
* **View Options:** Show/Hide detailed logs for Copying and Transcoding.
* **FFmpeg Inspector:** Check if your system supports Hardware Acceleration (NVENC/QSV).
* **Hardware Override:** Manually force GoPro/Android detection if auto-scan misses it.

---

## 📝 Change Log

### v4.13.5 (Current Release)
* **New Feature:** Added Native OS Notifications (Linux/macOS/Windows) and sound alerts when jobs complete.
* **New Feature:** Added "Verify Copy" toggle using xxHash64 (fast) or MD5 (fallback).
* **New Feature:** Added Pre-Flight Storage Check. The app now warns you if the destination is full before starting.
* **Improvement:** MTP "Sniper Mode" significantly speeds up scanning for Android phones and GoPros.
* **Improvement:** Restored Smart Network Filtering to
