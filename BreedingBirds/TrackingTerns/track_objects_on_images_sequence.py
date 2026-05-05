import os
import sys
import cv2
import shutil
import json
import numpy as np
from iou_boxes_manager import iouBoxesManager

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, os.pardir, os.pardir))
# Add the project root to the Python path
sys.path.append(project_root)
from Utilities.global_utils import GeneralUtils

trackId = 0


class TrackingObjectsInImagesSequence:
    
    def __init__(self, tracking_result_dir, MIN_TRACK_BOXES = 4):
        self._tracked_objects = []
        self._iou_box_manager = iouBoxesManager()
        self._tracking_result_dir = tracking_result_dir
        self._min_track_boxes = MIN_TRACK_BOXES
    
    def update_tracked_objects(self, predictions):
        if len(self._tracked_objects) == 0:
            # Create list for each box
            for prediction in predictions['predictions']:
                prediction['image_path'] = predictions['path']
                self._tracked_objects.append({'predictions': [prediction], 'iou': []})
            return

        # Mark the objects that a box already added to prevent double boxes addition
        objects_found_box = set()
        for prediction in predictions['predictions']:
            iou_in_all_object_boxes = [self._iou_box_manager.calc_iou_box_vs_boxes_seq(\
                self._tracked_objects[index]['predictions'], prediction) \
                       for index in range(0, len(self._tracked_objects))]

            # Find the index of the maximum value
            max_iou_index = max(enumerate(iou_in_all_object_boxes), key=lambda x: x[1])[0]
            max_iou = iou_in_all_object_boxes[max_iou_index]
            prediction['image_path'] = predictions['path']
            if max_iou > 0.4:
                if max_iou_index not in objects_found_box:
                    self._tracked_objects[max_iou_index]['predictions'].append(prediction)
                    self._tracked_objects[max_iou_index]['iou'].append(max_iou)
                    objects_found_box.add(max_iou_index)
            else:
                self._tracked_objects.append({'predictions': [prediction], 'iou': []})
    

    def make_report(self, flag_id, yolo_images_directory, frames_number):
        if len(self._tracked_objects) == 0:
            file_content = {
                "frames_number": frames_number,
                "object_boxes": []
            }

            # Save tracked objects to a JSON file
            with open(f'{self._tracking_result_dir}/flag{flag_id}.json', 'w') as json_file:
                json.dump(file_content, json_file, indent=4)
                return
        
        # Copy image to draw all object boxes on it
        image_name = os.path.basename(self._tracked_objects[0]['predictions'][0]['image_path'])

        GeneralUtils.copy_image(yolo_images_directory, self._tracking_result_dir ,image_name, \
                                f'flag{flag_id}.png')
                          
        self._tracked_objects = [tracked_object for tracked_object in self._tracked_objects \
                  if len(tracked_object['predictions']) >= self._min_track_boxes]
        
        for i, tracked_object in enumerate(self._tracked_objects):
            
            tracked_object['iou'] = sum(tracked_object['iou']) / len(tracked_object['iou']) if len(tracked_object['iou']) > 0 else 0
            
            global trackId
            tracked_object['id'] = trackId
            trackId += 1

            # Define one rectangles color for an object boxes sequence 
            color = GeneralUtils.colors_with_names[i % len(GeneralUtils.colors_with_names)][1]
            GeneralUtils.draw_boxes(tracked_object['predictions'], f'{self._tracking_result_dir}/flag{flag_id}.png', color, i)
        
        
        # Sort tracked objects from higher to lower length of bounding boxes
        file_content = {
            "frames_number": frames_number,
            "object_boxes": sorted(self._tracked_objects, key=lambda x: len(x['predictions']), reverse=True)
        }

        # Save tracked objects to a JSON file
        with open(f'{self._tracking_result_dir}/flag{flag_id}.json', 'w') as json_file:
            json.dump(file_content, json_file, indent=4)


    def get_tracked_objects(self):
        return self._tracked_objects
    

