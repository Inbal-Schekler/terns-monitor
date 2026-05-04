# Tern Colony Monitoring System

Automated system for detecting, counting, and mapping breeding seabirds at the Atlit colony (Israel), focusing on two endangered species: the **Common Tern** (*Sterna hirundo*) and the **Little Tern** (*Sternula albifrons*).

The system uses two PTZ cameras to scan the colony automatically, downloads the recordings from an NVR server, converts them to images, and runs a deep-learning pipeline to count and track terns. A second pipeline for detecting dead chicks is currently in development.

For a detailed description of the methods and results, see our paper.

---

## Repository Structure

```
terns-project-2025/
│
├── RealCoordinatesCalculator/   ← SHARED: PTZ scan control, camera calibration
├── ConvertVideoToImage/         ← SHARED: NVR download, video-to-image conversion
├── Utilities/                   ← SHARED: general helper functions
│
├── BreedingBirds/               ← Pipeline: counting and tracking breeding terns
│   ├── YoloDetector/
│   ├── TrackingTerns/
│   ├── ClassifyTerns/
│   ├── LabelsDistributionInFlags/
│   └── FinalResults/
│
└── Chicks/                      ← Pipeline: detecting dead chicks (work in progress)
    ├── YoloDetector/
    ├── TrackingTerns/
    ├── ClassifyTerns/
    └── FinalResults/
```

The first two steps (scanning and video-to-image conversion) are **shared** — they feed into both the BreedingBirds and Chicks pipelines. After that, each pipeline follows its own analysis path.

---

## Prerequisites

- **Python 3.x** (Anaconda recommended) with packages: `requests`, `opencv-python`, `ultralytics`
- **FFmpeg** installed at `C:\ffmpeg\bin\ffmpeg.exe`
- **Windows** (Task Scheduler is used for automation)
- Camera credentials stored in `RealCoordinatesCalculator/new_camera.ini` (not committed — see format at the bottom of this file)

---

## Step 0 — One-Time Setup: Automate Scanning and Download

Both the camera scan and the video download are fully automated via Windows Task Scheduler. Run each setup script **once** and they will run every day without manual intervention.

### 0a. Scan automation — `RealCoordinatesCalculator/`

**Script:** `setup_scan_tasks.ps1`  
Right-click → *Run with PowerShell*. This registers two daily tasks:

| Task | Trigger | What it does |
|------|---------|--------------|
| `TernScan_Morning` | 10:01 daily | Runs `run_scan.py` → full scan at 10:01:50 |
| `TernScan_Afternoon` | 15:01 daily | Runs `run_scan.py` → full scan at 15:01:50 |

`run_scan.py` controls the south camera (181) via ONVIF because we couldn't create scans on accurate times with the new south camera system from 2026. Each time it runs, it performs **two complete scan passes** with a 5.5-minute rest between them, so each video recording contains two extractable tours. The north camera (191) has its own internal schedule.

**Scan structure per session:**
- Pass 1 → Tour 1 (32 flags × 15s) + 10s gap + Tour 2 (15 flags × 15s) ≈ 12 min
- Rest: 329 seconds (~5.5 min)
- Pass 2 → same as Pass 1 ≈ 12 min
- Total: ~38 minutes per session

> **Note:** `new_camera.ini` must be present in `RealCoordinatesCalculator/` before running. See the Camera Connection section at the bottom.

### 0b. Download automation — `ConvertVideoToImage/`

**Script:** `setup_download_task.ps1`  
Right-click → *Run with PowerShell*. This registers two daily tasks:

| Task | Trigger | What it does |
|------|---------|--------------|
| `TernsCameraDownload_1030` | 10:30 daily | Downloads yesterday's scans for both cameras |
| `TernsCameraDownload_1530` | 15:30 daily | Same — catches any retries |

**Script:** `extrac_scans_auto.py`

Downloads scan videos from the NVR server (Nx Witness) for each camera:

| Camera | Retention on NVR | Days downloaded per run |
|--------|-----------------|------------------------|
| North (191) | ~1 day | 1 |
| South (181) | ~7 days | 7 |

The script skips files that already exist, so it is safe to run daily for both cameras. Videos are saved to:
```
F:\My Drive\tern_project\terns_movies\{year}\{camera_name}\
```

The south camera (181) delivers HEVC from the NVR and is automatically transcoded to H.264 (using FFmpeg) so files are seekable and play on all software.

---

## Step 1 — Video to Images — `ConvertVideoToImage/`

**Notebook:** `run_video_converter_2026.ipynb`

Converts each scan video into a folder of images — 8 images per flag position per tour — organized by camera, video, and tour.

### How it works (2026)

The 2026 converter uses an **OCR + absolute seeking** approach, which replaced the older frame-counting approach that accumulated timing drift across flags.

**Phase 1 — Find the scan start:**
EasyOCR reads the timestamp overlay burned into the video frames. The converter seeks forward through the video until it finds the exact scan start time defined in `known_scan_start_times` (e.g. `10:01:44` for camera 181 morning). This gives a precise anchor point in the video file.

**Phase 2 — Extract each flag independently:**
Each flag is extracted by seeking directly to an absolute millisecond position:
```
flag_position = scan_start_ms + flag_index × flag_length × 1000
```
The first 3 seconds of each flag's window are skipped (camera settling time), and then 8 frames are saved — one per second. Because every flag seeks independently from the same anchor, there is **no drift accumulation** across flags. An error at flag 20 has zero effect on flag 21.

**Two tours per video:**
The second tour uses the same logic with an offset of `num_flags × flag_length + magin_between_tours` seconds added to the anchor.

Each video produces:
```
ImagesDir/2026/{camera_id}/{video_name}/
    ├── tour0/
    │   ├── flag92_0_....jpg   ← 8 frames per flag (frame_0 to frame_7)
    │   ├── flag92_1_....jpg
    │   └── ...
    └── tour1/
        └── ...
```

### Pre-flight gap check

Before converting, always run a gap check on all videos of the day. NVR recording gaps (brief network interruptions) cause the camera to miss part of its scan, making that day unusable for monitoring.

In your Colab notebook, add this cell **before** the conversion loop:

```python
for date in dates:
    result = subprocess.run(
        f"python '{script_path}' --check {date.strip()}",
        shell=True, capture_output=True, text=True
    )
    print(result.stdout)
```

The check samples 3 OSD timestamps from each video via OCR and compares them to the expected times. If any timestamp is more than 5 seconds off, a gap is reported. Note: FFprobe-based PTS analysis does **not** work here because the NVR records the video container continuously even during interruptions — the gap only appears in the OSD content.

Output for a clean day:
```
Checking videos for 2026-05-04 ...
  Checking [181] atlitcam181.stream_2026_05_04_10_01_30.mkv ... OK
  Checking [181] atlitcam181.stream_2026_05_04_15_01_30.mkv ... OK
  Checking [191] atlitcam191.stream_2026_05_04_09_59_50.mkv ... OK
  Checking [191] atlitcam191.stream_2026_05_04_14_59_50.mkv ... OK

  All videos complete — safe to convert to images.
```

Output for a day with a gap:
```
#######################################################
#  WARNING: DO NOT USE 2026-04-30 FOR MONITORING  #
#######################################################
  Gap in: atlitcam181.stream_2026_04_30_10_01_30.mkv
    -> at scan +345s: expected 10:07:29, got 10:07:40 (11s off)
#######################################################
```

### Configuration — `tours_details.json`

| Field | Description |
|-------|-------------|
| `videos_dir` | Path to downloaded scan videos |
| `images_dir` | Output path for extracted images |
| `flags_ids` | Ordered list of flag numbers visited in one scan pass |
| `flag_length` | Duration of each flag position in the scan (seconds, currently 15) |
| `magin_between_tours` | Gap between tour 0 end and tour 1 start (seconds, currently 329 for camera 181) |

> **Important:** `magin_between_tours` must match `GAP_BETWEEN_SCANS` in `run_scan.py`. If you change the rest gap in the scan script, update this value too.

### Configuration — `run_video_converter.ini`

| Field | Description |
|-------|-------------|
| `dates` | Comma-separated list of dates to process, in `YYYY_MM_DD` format (e.g. `2026_04_30,2026_05_01`) |

### Running

1. Open `ConvertVideoToImage/run_video_converter_2026.ipynb` in Google Colab
2. Verify `videos_dir` and `images_dir` in `tours_details.json`
3. Set the dates in `run_video_converter.ini`
4. Run the gap check cell first — only proceed if all videos are clean
5. Run the conversion cells

---

## Step 2 — YOLO Detection — `BreedingBirds/YoloDetector/`

**Notebook:** `yolo_runner.ipynb`

Runs a trained YOLOv8 model on the extracted images to detect terns. Results are saved per image for use in the tracking step.

**Configuration:** `yolo_runner.ini`

| Field | Description |
|-------|-------------|
| `dates` | Dates to process |
| `images_dir` | Path to images from Step 1 |
| `result_dir` | Output path for YOLO detection results |
| `images_chunk_size` | Number of images per batch |

---

## Step 3 — Single-Scan Tracking — `BreedingBirds/TrackingTerns/`

**Notebook:** `track_scan_runner.ipynb`

Tracks individual terns across the images of one scan, linking detections into tracks.

**Configuration:** `track_scan_runner.ini`

| Field | Description |
|-------|-------------|
| `dates` | Dates to process |
| `yolo_result_dir` | Path to YOLO results from Step 2 |
| `tracker_result_dir` | Output path for single-scan tracks |

---

## From here: choose your pipeline

---

## Breeding Birds Pipeline — `BreedingBirds/`

### Option A — Daily Tern Count

**Step 4A: `BreedingBirds/ClassifyTerns/daily_count_terns.ipynb`**

Classifies and counts terns across all scans of one day. Aggregates results from multiple scan tracks.

**Configuration:** `daily_count_terns.ini`

| Field | Description |
|-------|-------------|
| `date` | Date to process |
| `classifier_model` | Path to trained classifier model |
| `tracker_result_dir` | Path to single-scan tracking results |
| `labels_distribution` | Path to label distribution statistics file |

---

### Option B — Breeding Tern Detection (multi-scan)

**Step 4B: `BreedingBirds/ClassifyTerns/classify_terns.ipynb`**

Classifies single-scan tracks. Uses YOLO outputs, track size (in cm), and location distribution as features.

**Configuration:** `classify_terns.ini`

| Field | Description |
|-------|-------------|
| `date` | Date to process |
| `classifier_model` | Path to trained classifier model |
| `one_scan_result_dir` | Path to single-scan tracking results |
| `classification_result_dir` | Output path for classification results |
| `labels_distribution` | Path to label distribution statistics file |

---

**Step 5B: `BreedingBirds/TrackingTerns/track_breeding_terns_runner.ipynb`**

Tracks terns across multiple scans. Breeding terns are identified by spatial fidelity — they return to the same location across scans.

**Configuration:** `track_breeding_terns_runner.ini`

| Field | Description |
|-------|-------------|
| `date` | Date to process |
| `one_scan_result_dir` | Path to single-scan tracking results |
| `mult_scans_result_dir` | Output path for multi-scan tracking results |
| `classification_result_dir` | Path to classification results |
| `video_converter_dir` | Path to images directory |

---

**Step 6B: `BreedingBirds/FinalResults/report_breeding_terns.ipynb`**

Classifies and counts breeding terns using multi-scan tracking data. Applies overlap correction between camera positions.

**Configuration:** `report_breeding_terns.ini`

| Field | Description |
|-------|-------------|
| `date` | Date to process |
| `breeding_tracks_dir` | Path to multi-scan tracking results |
| `final_report_dir` | Output path for final report |
| `overlap_areas` | Path to `overlap_areas.json` |

---

## Chicks Pipeline — `Chicks/` *(work in progress)*

This pipeline detects and counts dead chicks in the colony. Steps 0–1 (scanning and video-to-image conversion) are shared with the BreedingBirds pipeline. The analysis notebooks are in `Chicks/` and follow a similar structure.

---

## Camera Calibration — `RealCoordinatesCalculator/`

Each camera flag (preset position) is mapped from camera pixel space to physical coordinates on a drone image of the colony. This mapping is used to calculate bounding box sizes in centimeters and to correct for overlapping fields of view between flags.

See `RealCoordinatesCalculator/README.md` for full details on the calibration process, including the 2026 south camera replacement and recalibration.

Key outputs:
- `PTZCamValues181_mod.txt` — south camera world angles + focal length per flag
- `PTZCamValues191_mod.txt` — north camera world angles + focal length per flag
- `overlap_areas.json` — overlapping areas between flag positions (used in final count)

### Detecting overlaps between flag positions
**Notebook:** `detect_overlaps.ipynb`  
Identifies areas seen by more than one flag, to avoid double-counting terns. Saves results to `overlap_areas.json`.

---

## Model Training

### YOLOv8 — species detection
**Notebook:** `BreedingBirds/yolov8_costum_training.ipynb`  
Fine-tunes YOLOv8 to distinguish Common Terns from Little Terns using physical characteristics.

### Classifier — breeding vs non-breeding
Features used: YOLO outputs, track size (cm), movement rate, detection rate, location probability.

1. Run Steps 1–3 on scans where tagged birds were captured
2. Set parameters in `train_classifier.ini`
3. Open and run `train_classifier.ipynb`

---

## Camera Connection

Camera credentials are stored in `RealCoordinatesCalculator/new_camera.ini` (not committed to git).

Create the file with this format:
```ini
[General]
CAM_IP=2.54.101.27
CAM_PORT=8080
USER_NAME=admin
PASSWORD=your_password_here
```

NVR server: `212.179.113.90:7001` — credentials in `extrac_scans_auto.py`.
