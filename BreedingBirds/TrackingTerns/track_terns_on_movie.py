import os
import sys
import json
import argparse
import configparser

from collections import defaultdict
from track_objects_on_images_sequence import TrackingObjectsInImagesSequence

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, os.pardir, os.pardir))
# Add the project root to the Python path
sys.path.append(project_root)
from Utilities.global_utils import GeneralUtils


class TernsTrackerOnMovie:
    def __init__(self, yolo_result_dir, tracker_result_dir):
        # Directory path where the YOLO results
        self._yolo_jsons_directory = yolo_result_dir + "/Jsons"
        self._yolo_images_directory = yolo_result_dir + "/Images"
        # Directory path where tracker save results
        self._tracker_result_dir = tracker_result_dir
        # Create directory for tracking results
        GeneralUtils.create_directory(self._tracker_result_dir)        

        images_list = self._get_file_names(self._yolo_jsons_directory)
        self._image_list = sorted(images_list, key=GeneralUtils.extract_flag_and_image_numbers)

    def track_terns(self):
        # Each sublist contains images of the same camera position(flag).
        image_names_grouped = self._group_by_flag(self._image_list)
        
        for flag_id in image_names_grouped:
            self._track_and_report(flag_id, image_names_grouped[flag_id])
            

    def _track_and_report(self, flag_id, image_names):
        tracking_boxes_manager = TrackingObjectsInImagesSequence(self._tracker_result_dir)

        for image_name in image_names:
            with open(self._yolo_jsons_directory + '/' + image_name, "r", encoding="cp866") as file:

                # Parse the JSON data from the file
                yolo_json_result = json.load(file)
            
            tracking_boxes_manager.update_tracked_objects(yolo_json_result)
        
        tracking_boxes_manager.make_report(flag_id, self._yolo_images_directory, len(image_names))
        
    
    # This fucntion group the images by flag ids
    def _group_by_flag(self, file_names):
        grouped_files = defaultdict(list)
        for file_name in file_names:
            x_value = file_name.split('_')[0][4:]
            grouped_files[x_value].append(file_name)

        # Convert the defaultdict to a list of lists
        return grouped_files

    def _get_file_names(self, folder_path):
        try:
            # List all files in the given folder
            files = [entry.name for entry in os.scandir(folder_path) if entry.is_file()]
            return files
        except FileNotFoundError:
            print(f"Error: Folder '{folder_path}' not found.")
            return []
        
    def _get_numeric_part(self, filename):
        # Get the basename of the file (without the directory path and extension)
        basename = os.path.basename(filename)
        # Extract the numeric part from the filename by splitting on "_", taking the first part, and converting it to an integer
        return int(basename.split("_")[0])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-y', '--yolo_result_tour_dir', help='Yolo detection result directory of specific tour')
    args = parser.parse_args()
    # Read the directory path where images located
    yolo_result_tour_dir = args.yolo_result_tour_dir

    config = configparser.ConfigParser()
    # Read the config file
    config.read('track_scan_runner.ini', encoding="utf8")
    # Access values from the config file
    yolo_result_dir = config.get('General', 'yolo_result_dir')
    tracker_result_dir = config.get('General', 'tracker_result_dir')

    
    terns_tracker = TernsTrackerOnMovie(f'{yolo_result_dir}/{yolo_result_tour_dir}', \
                                        f'{tracker_result_dir}/{yolo_result_tour_dir}')

    terns_tracker.track_terns()
