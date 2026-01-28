# CineBridge Pro v4.17.7 Development Roadmap
**Focus:** Reliability, Quality, and Customization.

## 1. Robust Device Detection (User Critical)
**Goal:** Stop relying solely on folder structures. Use system-level identifiers.
- [ ] **Linux `lsblk` Integration:** Use `lsblk -o NAME,LABEL,UUID,MOUNTPOINT` to identify drives by Volume Label (e.g., "DJI_OSMO", "Sandisk_Extreme").
- [ ] **Metadata Fallback:** Improve `MediaInfoExtractor` to handle cases where `ffprobe` might not find the `model` tag or where the tag format differs (e.g., DJI Action 5 vs Neo).
- [ ] **Registry Logic:** Update `DeviceRegistry.identify()` to prioritize Volume Label > Metadata > Folder Structure.

## 2. Delivery Tab Overhaul
**Goal:** Fix render failures and improve quality control.
- [ ] **Fix H.264 Failure:** Correct the extension logic (`.mp4` vs `.mov`) and ensure `h264_nvenc` commands are valid.
- [ ] **H.265 Quality Fix:**
  - Implement Rate Control for NVENC (CQP or VBR instead of default).
  - Add explicit "Bitrate" or "Quality" slider.
- [ ] **Encoder Selection:** Allow users to force "Software Encoding (CPU)" even if a GPU is detected, to prioritize quality over speed.
- [ ] **Error Reporting:** Capture and display `stderr` when a render fails instantly.

## 3. Ingest Folder Customization
**Goal:** Allow "Source" and "Edit Ready" media to be organized effectively for NLEs (Resolve).
- [ ] **Path Builder UI:** Create a dialog to configure:
  - **Source Structure:** e.g., `{Project}/Source/{Camera}/...`
  - **Transcode Structure:** e.g., `{Project}/Proxies/{Camera}/...`
- [ ] **Token System:** Support tokens like `{Date}`, `{Camera}`, `{Resolution}`, `{Category}`.

## 4. Debugging & Transparency
- [ ] **Real-time Log View:** Add a "Show Log" button to the Dashboard to see the underlying FFmpeg process output (stderr) in real-time.
