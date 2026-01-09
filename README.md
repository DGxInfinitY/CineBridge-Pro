# CineBridge Pro: The Linux DIT Suite

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20Windows%20%7C%20macOS-lightgrey.svg)]()

**CineBridge Pro** is an open-source Digital Imaging Technician (DIT) tool designed to solve the "Resolve on Linux" problem. It handles secure media offloading, checksum verification, and edit-ready transcoding (DNxHR/ProRes) in a single, streamlined interface.

![CineBridge Pro Screenshot](assets/screenshot.png) ---

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
Don't want to mess with Python? Download the standalone executable for your operating system.

* **[Download Latest Release (Linux AppImage / Windows .exe)](https://github.com/DGxInfinitY/CineBridge-Pro/releases/latest)**
* *Note: AppImages on Linux may require you to right-click -> Properties -> Permissions -> "Allow executing file as program".*

### 🛠️ Manual Build (Source Code)
If you want the absolute latest features or need to modify the code, run it directly from source.

**1. Clone the Repository:**
```bash
git clone [https://github.com/DGxInfinitY/CineBridge-Pro.git](https://github.com/DGxInfinitY/CineBridge-Pro.git)
cd CineBridge-Pro
