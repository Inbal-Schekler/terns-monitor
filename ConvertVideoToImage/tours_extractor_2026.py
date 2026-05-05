import os
import re
import json
import argparse
import sys

from pathlib import Path
from datetime import datetime

from video_converter_2026 import VideoConverter, check_for_gaps, known_scan_start_times


def get_tour_details(video_path, tours_details):
    pattern = r'atlit(?:cam)?(\d+)'
    match = re.search(pattern, video_path)

    if match:
        camera_id = match.group(1)
        specific_cam_details = None
        for _, cam_details in tours_details.items():
            if cam_details["camera_id"] == int(camera_id):
                specific_cam_details = cam_details
                break
        if specific_cam_details is None:
            raise ValueError("Camera ID not found in tours_details")
    else:
        raise ValueError("Camera ID could not be extracted from filename")

    flags_ids = specific_cam_details['flags_ids']
    tour_length = specific_cam_details['tour_length']
    magin_between_tours = specific_cam_details['magin_between_tours']
    margin_till_1st_tour = specific_cam_details['margin_till_1st_tour']
    flags_to_shelve = specific_cam_details.get('flags_to_shelve', [])
    flag_length = specific_cam_details['flag_length']
    settle_seconds = specific_cam_details.get('settle_seconds', 3)

    return (flags_ids, tour_length, margin_till_1st_tour, magin_between_tours, flags_to_shelve, flag_length, settle_seconds)


def check_day_videos(date_str, videos_dir, tours_details):
    """
    Checks all videos for a given date (format: YYYY_MM_DD) across all cameras.
    Prints a clean summary and returns True if all videos are complete.
    """
    date_display = date_str.replace('_', '-')
    print(f"\nChecking videos for {date_display} ...")

    all_ok = True
    found_any = False
    bad_videos = []

    for cam_key, cam_details in tours_details.items():
        cam_id = str(cam_details['camera_id'])
        cam_dir = Path(videos_dir) / cam_id

        if not cam_dir.exists():
            continue

        matches = sorted(cam_dir.glob(f'*{date_str}*.mkv'))
        if not matches:
            print(f"  Camera {cam_id}: no videos found")
            all_ok = False
            continue

        flag_length = cam_details['flag_length']
        num_flags = len(cam_details['flags_ids'])

        for video_path in matches:
            found_any = True
            # Detect morning vs afternoon from the hour in the filename
            hour_match = re.search(r'_(\d{2})_\d{2}_\d{2}\.mkv$', video_path.name)
            hour = int(hour_match.group(1)) if hour_match else 0
            scan_type = "noon" if hour >= 12 else "morning"
            scan_start_time_str = known_scan_start_times[cam_id][scan_type]

            print(f"  Checking [{cam_id}] {video_path.name} ... ", end='', flush=True)
            gaps = check_for_gaps(str(video_path), cam_id, scan_start_time_str, flag_length, num_flags)

            if gaps:
                all_ok = False
                bad_videos.append((video_path.name, gaps))
                print(f"GAP FOUND")
            else:
                print(f"OK")

    print()
    if not found_any:
        print("No videos found for this date.")
        return False
    elif all_ok:
        print(f"  All videos complete — safe to convert to images.")
    else:
        print("#" * 55)
        print(f"#  WARNING: DO NOT USE {date_display} FOR MONITORING  #")
        print("#" * 55)
        for name, gaps in bad_videos:
            print(f"  Gap in: {name}")
            for g in gaps:
                print(f"    -> at scan +{g['at_s']}s: expected {g['expected']}, got {g['actual']} ({g['diff_s']:.0f}s off)")
        print("#" * 55)
    print(f"{'='*55}\n")

    return all_ok


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-r', '--video_name', help='Name of a single video to convert')
    parser.add_argument('-c', '--check', help='Check all videos for a date (YYYY_MM_DD) before converting')
    args = parser.parse_args()

    json_path = os.path.abspath('tours_details.json')
    with open(json_path, 'r', encoding='utf-8') as config_file:
        tour_configuration = json.load(config_file)

    videos_dir = Path(tour_configuration["videos_dir"])

    if args.check:
        check_day_videos(args.check, videos_dir, tour_configuration['tours_details'])
        exit()

    video_name = args.video_name
    if not video_name:
        print("Please provide --video_name or --check <date>")
        exit()

    if not videos_dir.exists() or not videos_dir.is_dir():
        print(f'{videos_dir} - Movies directory path does not exist.')
        exit()

    video_path = str(videos_dir / video_name)

    video_converter = VideoConverter()
    (flags_ids, tour_length, margin_till_1st_tour, magin_between_tours, flags_to_shelve, flag_length, settle_seconds) = \
        get_tour_details(video_path, tour_configuration['tours_details'])

    if flags_ids is None or tour_length is None:
        print("❌ Could not extract tour details — exiting.")
        sys.stdout.flush()
        exit()

    video_converter.convert_video(video_path, flags_ids, tour_length, magin_between_tours,
                                  margin_till_1st_tour, flags_to_shelve, flag_length, settle_seconds,
                                  tour_configuration['images_dir'])
