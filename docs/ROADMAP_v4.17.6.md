# CineBridge Pro v4.17.6 Development Roadmap
**Focus:** UI Refinements, Workflow Optimization, and Dashboard Consolidation.

## 1. Dashboard & Hardware Monitor Overhaul
**Goal:** Optimize vertical space and group related real-time metrics.
- [x] **Consolidate UI:** Move Hardware Monitor (CPU/GPU) data from its own isolated row to the same line as the Transcode Metrics (FPS | Speed).
- [x] **Layout:** Create a unified `DashFrame` status line:
  `[ Transcoding File 2/10 ] [ 🎬 24 fps | 1.5x Speed ] [ CPU: 45% | GPU: 60% ]`
- [x] **Implementation:** Modify `src/modules/tabs/ingest.py` to merge `self.stats_row` and `self.transcode_metrics_label` into a single responsive layout.

## 2. Enhanced Progress Tracking
**Goal:** Provide granular feedback during the two-stage Ingest process (Copy -> Transcode).
- [x] **File Progress Indicator:** Update the "Found (x) Files" label dynamically during transfer:
  - *Current:* "Found 50 Files" (Static).
  - *New:* "Copied 15/50 Files (30%)".
- [x] **Transcode Progress Counter:** Add a specific "Transcoding File X of Y" indicator to the dashboard.
- [x] **Dual-Stage Progress Bar:**
  - *Phase 1 (Copy):* Bar tracks byte-level copy progress (0-100%).
  - *Phase 2 (Transcode):* Instead of resetting or staying at 100%, the bar should switch to tracking the *percentage of transcode jobs completed* or the *progress of the current file*.

## 3. Logging & Feedback
**Goal:** Improve transparency for debugging and user confidence.
- [x] **Verbose Transcode Logs:** Update `src/modules/workers/transcode.py` to emit clearer, detailed logs (e.g., specific FFmpeg arguments, per-file success/failure with duration).
- [x] **Standardized Dialogs:** Ensure all "Job Complete" or "Error" dialogs use the standard `JobReportDialog` or `SystemNotifier` for consistent look and feel.
- [x] **Error Clarity:** Refine error messages in `CopyWorker` and `AsyncTranscoder` to be less technical and more actionable.

## 4. UI Polish
- [x] **Alignment:** Audit `ingest.py`, `convert.py`, and `delivery.py` to ensure vertical alignment of top-level widgets.
- [x] **Tab Flow:** Review navigation order (Tab order) for keyboard accessibility.

## 5. Device Identification (User Request)
- [x] **Granular Detection:** Detect DJI Neo 2 and Action 5 Pro specifically.
- [x] **User Overrides:** Allow manual renaming of devices with persistent storage.
- [x] **Inline Editing:** Replaced buttons with clean click-to-rename text interaction.
- [x] **Metadata Refinement:** Use internal model ID for identification and override keys.

## 6. Documentation
- [x] Update `README.md` and `ARCHITECTURAL_OVERVIEW.md` to reflect the new dashboard layout and progress logic.
