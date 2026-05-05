import os
import sys
import cv2
import re
import json
import subprocess
import easyocr
from collections import defaultdict
from datetime import datetime


def check_for_gaps(video_path, camera_id, scan_start_time_str, flag_length, num_flags,
                   gap_threshold_seconds=5.0):
    """
    Samples OSD timestamps at 3 points through tour 1 and checks they match expected times.
    Returns list of gap dicts if gaps found, empty list if OK.
    All intermediate OCR output is suppressed — only the result is printed.
    """
    import contextlib, io
    from datetime import timedelta

    video = cv2.VideoCapture(video_path)
    fps = int(round(video.get(cv2.CAP_PROP_FPS)))

    vc = VideoConverter()
    with contextlib.redirect_stdout(io.StringIO()):
        found = vc._skip_until_timestamp(video, camera_id, scan_start_time_str, video_path, fps)

    if not found:
        print(f"  SKIP — could not find scan start in {os.path.basename(video_path)}")
        video.release()
        return []

    scan_start_ms = video.get(cv2.CAP_PROP_POS_MSEC)
    scan_start_time = datetime.strptime(scan_start_time_str, "%H:%M:%S")
    tour_duration_s = num_flags * flag_length
    check_offsets = [tour_duration_s // 4, tour_duration_s // 2, tour_duration_s * 3 // 4]

    gaps = []
    for offset_s in check_offsets:
        video.set(cv2.CAP_PROP_POS_MSEC, scan_start_ms + offset_s * 1000)
        ret, frame = video.read()
        if not ret:
            continue
        ts = extract_timestamp_easyocr(frame)
        if ts is None:
            continue
        expected = (datetime.combine(datetime.today(), scan_start_time.time())
                    + timedelta(seconds=offset_s)).time()
        actual = ts.time()
        diff = abs((datetime.combine(datetime.today(), actual)
                    - datetime.combine(datetime.today(), expected)).total_seconds())
        if diff > gap_threshold_seconds:
            gaps.append({'at_s': offset_s, 'expected': str(expected),
                         'actual': str(actual), 'diff_s': diff})

    video.release()
    return gaps

# camera_move_time no longer used in main loop (kept for reference)
# camera_move_time = defaultdict(lambda: 2, {
#     27:5, 40: 4, 45: 4, 49: 6, 52: 6, 57: 4, 59: 4, 68: 5, 70:4, 71: 4, 72:5, 4: 5, 79: 4, 82: 5, 84: 5,
#     94:3, 101:3, 103:3, 109:3, 110: 3, 111: 6, 117: 7, 119: 7, 123: 9, 127: 5, 136: 4
# })

# max_displayed_frames no longer used in main loop (kept for reference)
# max_displayed_frames = defaultdict(lambda: 11, {
#     73:9, 128:10, 138: 9
# })
# max_displayed_frames = defaultdict(lambda: 7, {
#     73:7, 128:7, 138: 7
# })

known_scan_start_times = {
    #"191": {"morning": "09:59:50", "noon": "14:59:50"},
    "191": {"morning": "10:00:10", "noon": "14:59:50"},
    #"181": {"morning": "10:01:50", "noon": "15:01:50"},
    "181": {"morning": "10:01:44", "noon": "15:01:42"},
}

reader = easyocr.Reader(['en'])


def normalize_timestamp_text(text):
    text = text.replace('*', ':').replace('/', '-').replace('–', '-').replace('—', '-')
    text = re.sub(r'[^0-9:\-.\s]', '', text)
    text = text.replace('.', ':')
    text = re.sub(r'\s+', ' ', text).strip()

    patterns = [
        (re.search(r'(\d{4})[-/](\d{2})[-/](\d{2})[^\d]?(\d{2}):(\d{2}):(\d{2})', text), '%Y-%m-%d %H:%M:%S', lambda g: f"{g[0]}-{g[1]}-{g[2]} {g[3]}:{g[4]}:{g[5]}"),
        (re.search(r'(\d{2})[-/](\d{2})[-/](\d{4})[^\d]?(\d{2}):(\d{2}):(\d{2})', text), '%d-%m-%Y %H:%M:%S', lambda g: f"{g[0]}-{g[1]}-{g[2]} {g[3]}:{g[4]}:{g[5]}"),
        (re.search(r'(\d{2})(\d{2})(\d{4})\s*(\d{2}):(\d{2}):(\d{2})', text),             '%d-%m-%Y %H:%M:%S', lambda g: f"{g[0]}-{g[1]}-{g[2]} {g[3]}:{g[4]}:{g[5]}"),
    ]

    for pattern, fmt, build in patterns:
        if pattern:
            try:
                return datetime.strptime(build(pattern.groups()), fmt)
            except ValueError:
                continue

    return None


def extract_timestamp_easyocr(frame, debug=False):
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = w - 430, 0, w, 60
    cropped = frame[y1:y2, x1:x2]
    result = reader.readtext(cropped, detail=0)
    text = " ".join(result)
    if debug:
        print(f"  [OCR raw] '{text}'")
    return normalize_timestamp_text(text)


class VideoConverter:
    def _seconds_to_frames(self, seconds, fps):
        return int(seconds * fps)

    def _skip_seconds(self, video, seconds, fps):
        for _ in range(self._seconds_to_frames(seconds, fps)):
            ret, _ = video.read()
            if not ret:
                break

    def _skip_until_timestamp(self, video, camera_id, target_time_str, video_path, fps):
        target_time = datetime.strptime(target_time_str, "%H:%M:%S")
        print(f"Target time: {target_time.time()}")

        max_checks = 60
        first_detected_ts = None
        last_valid_frame_pos = None
        last_valid_time = None

        for check_num in range(max_checks):
            frame = None
            for _ in range(fps):
                ret, last_read_frame = video.read()
                if not ret:
                    print("End of video reached before finding timestamp.")
                    return False
                frame = last_read_frame

            ts = extract_timestamp_easyocr(frame, debug=(check_num < 5))
            if not ts:
                print(f"  [check {check_num}] OCR read nothing parseable")
            if ts:
                detected_time = ts.time()
                if not first_detected_ts:
                    first_detected_ts = detected_time

                if detected_time == target_time.time():
                    print(f"First detected timestamp: {first_detected_ts}")
                    print(f"Reached target timestamp: {detected_time}")
                    return True

                if detected_time < target_time.time():
                    last_valid_time = detected_time
                    last_valid_frame_pos = video.get(cv2.CAP_PROP_POS_FRAMES)

                if detected_time > target_time.time():
                    break

        if last_valid_time and last_valid_frame_pos is not None:
            print(f"First detected timestamp: {first_detected_ts}")
            print(f"Couldn't reach exact time. Rewinding to {last_valid_time}, frame {int(last_valid_frame_pos)}")
            video.set(cv2.CAP_PROP_POS_FRAMES, last_valid_frame_pos)
            t1 = datetime.combine(datetime.today(), last_valid_time)
            t2 = datetime.combine(datetime.today(), target_time.time())
            seconds_to_skip = (t2 - t1).total_seconds()
            print(f"Skipping ahead by {seconds_to_skip:.2f} seconds to reach target.")
            self._skip_seconds(video, seconds_to_skip, fps)
            return True

        if first_detected_ts:
            print(f"First detected timestamp: {first_detected_ts}")
        print(f"Target timestamp {target_time.time()} not found or approximated.")
        return False

    def convert_video(self, video_path, flags_ids, tour_length, magin_between_tours,
                      margin_till_1st_tour, flags_to_shelve, flag_length, settle_seconds, output_dir):
        video = cv2.VideoCapture(video_path)
        fps = int(round(video.get(cv2.CAP_PROP_FPS)))
        print(f"Video FPS detected: {fps}")

        video_name = os.path.splitext(os.path.basename(video_path))[0]
        match = re.search(r'atlitcam(\d+)', video_name)
        camera_id = match.group(1) if match else 'unknown'

        hour_guess = int(video_name.split("_")[4])
        scan_type = "noon" if hour_guess >= 12 else "morning"
        target_time_str = known_scan_start_times[camera_id][scan_type]

        check_for_gaps(video_path, camera_id, target_time_str, flag_length, len(flags_ids))

        if not self._skip_until_timestamp(video, camera_id, target_time_str, video_path, fps):
            print("Skipping conversion due to invalid timestamp.")
            sys.exit(1)

        scan_start_ms = video.get(cv2.CAP_PROP_POS_MSEC)
        print(f"Scan start position in video: {scan_start_ms/1000:.2f}s")

        print(f"Settle seconds: {settle_seconds}, frames per flag: 8")
        frames_per_flag = 8  # number of frames to capture per flag

        main_dir = f'{output_dir}/{camera_id}/{video_name}'
        os.makedirs(main_dir, exist_ok=True)
        print(f"Created main directory: {main_dir}")
        sys.stdout.flush()

        for tour_num in range(2):
            tour_offset_ms = 0
            if tour_num > 0:
                tour_offset_ms = (len(flags_ids) * flag_length + magin_between_tours) * 1000

            tour_dir = f'{output_dir}/{camera_id}/{video_name}/tour{tour_num}/'
            os.makedirs(tour_dir, exist_ok=True)
            print(f"Created tour directory: {tour_dir}")
            sys.stdout.flush()

            for flag_idx, flag_id in enumerate(flags_ids):
                flag_start_ms = scan_start_ms + tour_offset_ms + (flag_idx * flag_length + settle_seconds) * 1000

                for frame_num in range(frames_per_flag):
                    capture_ms = flag_start_ms + frame_num * 1000
                    video.set(cv2.CAP_PROP_POS_MSEC, capture_ms)
                    ret, curr_frame = video.read()
                    if not ret:
                        print(f"Could not read frame at {capture_ms/1000:.1f}s for flag {flag_id}")
                        break
                    filename = f"flag{flag_id}_{frame_num}_{video_name}.jpg"
                    if flag_id not in flags_to_shelve:
                        cv2.imwrite(f'{tour_dir}{filename}', curr_frame)

            print(f"Tour {tour_num} complete ({len(flags_ids)} flags)")

        # --- OLD frame-counting approach (kept for reference) ---
        # for tour_num in range(2):
        #     if tour_num > 0:
        #         self._skip_seconds(video, magin_between_tours, fps)
        #     frame_num = 0
        #     frames_counter = 0
        #     flag_num = 0
        #     while flag_num < len(flags_ids):
        #         ret, curr_frame = video.read()
        #         if not ret:
        #             break
        #         if frames_counter % fps == 0:
        #             filename = f"flag{flags_ids[flag_num]}_{int(frame_num)}_{video_name}.jpg"
        #             if flags_ids[flag_num] not in flags_to_shelve:
        #                 cv2.imwrite(f'{tour_dir}{filename}', curr_frame)
        #             frame_num += 1
        #         if frame_num > max_displayed_frames[flags_ids[flag_num]]:
        #             self._skip_seconds(video, camera_move_time[flags_ids[flag_num]] + 7.34 - 0.461, fps)
        #             flag_num += 1
        #             frame_num = 0
        #             frames_counter = -1
        #         frames_counter += 1

        video.release()
