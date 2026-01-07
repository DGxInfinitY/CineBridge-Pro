# 🌉 CineBridge Pro
### The Open Source DIT & Post-Production Suite

<p align="center">
  <img src="assets/icon.svg" width="150" height="150" alt="CineBridge Pro Logo">
</p>

<p align="center">
  <a href="#-download">Download</a> •
  <a href="#-features">Features</a> •
  <a href="#-why-cinebridge">Why CineBridge?</a> •
  <a href="#-build-from-source">Build from Source</a>
</p>

---

## 📥 Download
Pre-compiled binaries are available for **Linux (.deb)** and **Windows (.exe)**.

### [🚀 Click Here to Download Latest Release](https://github.com/DGxInfinitY/cinebridge/releases/latest)

> **Note:** macOS builds are currently experimental. Please build from source if a release is unavailable.

---

## 🎬 Why CineBridge?
CineBridge Pro was born out of frustration with video ingestion on Linux. Managing footage from GoPros, Drones, and Cinema Cameras on Ubuntu often meant dealing with slow transfer speeds, messy file structures, and codecs (like H.265) that stutter or wont even work in DaVinci Resolve on Linux (Free Version).

**CineBridge Pro solves this by automating the entire workflow:**
1.  **Ingest:** Auto-detects your camera cards and offloads footage into organized, date-stamped folders.
2.  **Transcode:** Automatically converts difficult codecs into **Edit-Ready DNxHR or ProRes** proxies during the copy process.
3.  **Deliver:** Provides a simple "Delivery Tab" to render your massive master files into web-optimized H.264/H.265 for YouTube or clients.

It creates a seamless bridge between your camera and your NLE (Non-Linear Editor).

---

## ✨ Features
* **Smart Ingest:** Auto-detects cameras (GoPro, DJI, Insta360) and drives.
* **Recursive Scanning:** Finds media files deep inside obscure folder structures.
* **Auto-Organization:** Sorts media by `Date / Camera / FileType` (Video, Photo, Raw).
* **Hybrid Transcoding:** Uses **NVIDIA (CUDA), Intel (QSV), or AMD (VAAPI)** hardware acceleration to decode footage, ensuring maximum speed.
* **Edit-Ready Proxies:** Generates professional DNxHR (Linux-friendly) or ProRes (Mac-friendly) intermediate files.
* **Duplicate Detection:** Skips files that have already been backed up.
* **Batch Convert:** Drag-and-drop tab for mass transcoding existing footage.
* **Delivery Tab:** One-click rendering for final delivery (YouTube 4K, 1080p, Socials).

---

## 🛠 Build from Source

If you prefer to run the raw Python code or build it yourself, follow these steps.

### Prerequisites
* **Python 3.10+**
* **FFmpeg** (Must be installed on your system path)

### 🐧 Linux (Ubuntu/Debian)
1.  **Install System Dependencies:**
    ```bash
    sudo apt update
    sudo apt install python3-pip ffmpeg
    ```
2.  **Clone & Install Requirements:**
    ```bash
    git clone [https://github.com/YourUsername/CineBridgePro.git](https://github.com/YourUsername/CineBridgePro.git)
    cd CineBridgePro
    pip install -r requirements.txt
    ```
3.  **Run:**
    ```bash
    python3 src/cinebridge.py
    ```

### 🪟 Windows
1.  **Install FFmpeg:** Download from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) and add `ffmpeg.exe` to your System PATH (or place it in a `bin/` folder inside `src/`).
2.  **Install Python:** Download Python 3.10+ from python.org.
3.  **Install Dependencies:**
    Open PowerShell/Command Prompt:
    ```powershell
    pip install -r requirements.txt
    ```
4.  **Run:**
    ```powershell
    python src/cinebridge.py
    ```

### 🍎 macOS
1.  **Install FFmpeg:**
    ```bash
    brew install ffmpeg
