import os
import re
import sys
import json
import configparser

from iou_boxes_manager import iouBoxesManager
from track_boxes_across_movies import TrackBoxesAcrossMovies

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, os.pardir, os.pardir))
# Add the project root to the Python path
sys.path.append(project_root)

from Utilities.global_utils import GeneralUtils

class NestedTernsTracker:
    def __init__(self):
        self._iou_box_manager = iouBoxesManager()

    def _update_assosiation(self, objects_assosiation, new_assosiations):
        if len(objects_assosiation) == 0:
            return new_assosiations
        # concatenate new assosiations to objects_assosiation
        for object_assosiation in objects_assosiation:
            for new_assosiation in new_assosiations:
                if object_assosiation[-1] == new_assosiation[0]:
                    object_assosiation.append(new_assosiation[1])

        return objects_assosiation


    def track_breeding_terns(self, movies_names, one_scan_result_dir, mult_scans_result_dir, video_converter_dir, classif_dir):
        nests_count = 0
        # Get flags list from tracking on movie result directory
        flags_list = [os.path.splitext(file)[0] for file in os.listdir(f'{one_scan_result_dir}/{movies_names[0]}')\
                      if file.endswith(".png")]

        for flag in flags_list:
            # Get all tracked terns(in jsons) of the specific flag 
            tracked_terns_jsons = [f'{one_scan_result_dir}/{movie_name}/{flag}.json' \
                                   for movie_name in movies_names]

            track_boxes_across_movies = TrackBoxesAcrossMovies()
            
            # Each cell have tracked objects in a single scan
            tracked_objects_in_all_movies = []
            # Load all json files of tracked objects
            for tracked_terns_json in tracked_terns_jsons:
                # Skip to the next tour file if the tour does not have the file
                if not os.path.exists(tracked_terns_json):
                    continue

                with open(tracked_terns_json, "r") as tracked_terns_json:
                    tracked_objects_json = json.load(tracked_terns_json)
                    tracked_objects = [tracked_object['predictions'] for tracked_object in tracked_objects_json["object_boxes"] if len(tracked_object['predictions']) > 3]
                    tracked_objects_in_all_movies.append(tracked_objects)
                    
            # Holds assosiation of the same objects from different movies
            objects_assosiations = []
            # Loop in each tracked object json and assosiate new objects with its object in previous movies
            for i in range(len(tracked_objects_in_all_movies)):
                # Returns pair indexes list of tracked object which are of the same object
                objects_assosiations = track_boxes_across_movies.assosiate_tracked_objects(tracked_objects_in_all_movies[i], \
                                                                            tracked_objects_in_all_movies[:i], objects_assosiations)

            # Shelve sequence that don't have suits in other scans
            objects_assosiations = [arr for arr in objects_assosiations if sum(value != -1 for value in arr) > len(arr) // 2]
            
            nests_count += len(objects_assosiations)

            # Extract the date from the movie name
            dir_name = self._get_movie_date(movies_names[0])
            # Extract the camera number from the movie name
            cam_number = self._get_camera_number(movies_names[0])
            dir_name = f'{dir_name}_{cam_number}'

            result_dir = f'{mult_scans_result_dir}/{dir_name}'
            # Make a flag report
            self._report_flag_nests(movies_names, f'{result_dir}/{flag}', tracked_terns_jsons, objects_assosiations, video_converter_dir, classif_dir)

        # Short report for nests total ammount
        nests_amount_json = {
            'total_nests': nests_count
        }

        with open(f'{result_dir}/report.json', 'w') as json_file:
            json.dump(nests_amount_json, json_file, indent=4)


    def _get_camera_number(self, movie_name):
        # Regular expression pattern to extract the number
        pattern = r'\d+'
        # Using re.findall() to extract all the numbers from the string
        numbers = re.findall(pattern, movie_name)
        # Extracted numbers will be in string format, so convert it to integers if needed
        if numbers:
            return int(numbers[0])
        else:
            print(f'Error - The movie name({movie_name}) does not have camera number in the format expected.')
            exit()



    def _get_movie_date(self, movie_name):
        # Regular expression pattern to extract the date
        pattern = r"\d{4}_\d{2}_\d{2}"
        # Extract date of the first movie according to the movie name
        movie_date = re.search(pattern, movie_name)
        if movie_date:
            return movie_date.group()
        else:
            print(f'Error - The movie name({movie_name}) does not have date in the format expected.')
            exit()


    def _calc_box_location_average(self, tracked_object):
        # Initialize variables to store sum of coordinates
        total_x1 = total_x2 = total_y1 = total_y2 = 0

        # Iterate over the list of objects and calculate the sum of coordinates
        for obj in tracked_object:
            box = obj["box"]
            total_x1 += box["x1"]
            total_x2 += box["x2"]
            total_y1 += box["y1"]
            total_y2 += box["y2"]
        
        # Calculate the average coordinates
        num_objects = len(tracked_object)
        average_x1 = total_x1 / num_objects
        average_x2 = total_x2 / num_objects
        average_y1 = total_y1 / num_objects
        average_y2 = total_y2 / num_objects
        
        # Return the average coordinates as a dictionary
        return { "x1": average_x1, "x2": average_x2, "y1": average_y1, "y2": average_y2 }

    def _aggregate_classes_freq(self, tracked_object):
        # Initialize a dictionary to store the sum of confidences and count of predictions for each class
        class_confidences = {}

        # Iterate over the boxes and aggregate the confidences for each class
        for box in tracked_object:
            box_class = box["name"]
            confidence = box["confidence"]
            if box_class in class_confidences:
                class_confidences[box_class]["sum_confidence"] += confidence
                class_confidences[box_class]["count"] += 1
            else:
                class_confidences[box_class] = {"sum_confidence": confidence, "count": 1}
        
        # Calculate the average confidence for each class
        class_average_confidences = {}
        for class_name, data in class_confidences.items():
            class_average_confidences[class_name] = {
                'conf': data["sum_confidence"] / data["count"] if data["count"] > 0 else 0.0,
                'weight': data["count"]
            }
        
        return class_average_confidences
    

    def _count_object_classes(self, tracked_object):
        # Initialize dictionary to store counts of classes
        classes_count = {}

        # Iterate over the boxes and count the classes of each category
        for box in tracked_object:
            box_class = box["name"]
            if box_class in classes_count:
                classes_count[box_class] += 1
            else:
                classes_count[box_class] = 1
        
        return classes_count
          
    
    def _calc_weighted_average_box(self, objects_location_average):
        weighted_sum_x1 = weighted_sum_x2 = weighted_sum_y1 = weighted_sum_y2 = total_weight = 0

        for item in objects_location_average:
            weight = item['weight']
            total_weight += weight
            weighted_sum_x1 += item['box_location_avg']['x1'] * weight
            weighted_sum_x2 += item['box_location_avg']['x2'] * weight
            weighted_sum_y1 += item['box_location_avg']['y1'] * weight
            weighted_sum_y2 += item['box_location_avg']['y2'] * weight

        if total_weight > 0:
            weighted_average_x1 = weighted_sum_x1 / total_weight
            weighted_average_x2 = weighted_sum_x2 / total_weight
            weighted_average_y1 = weighted_sum_y1 / total_weight
            weighted_average_y2 = weighted_sum_y2 / total_weight
            weighted_average_box = {
                "x1": weighted_average_x1,
                "x2": weighted_average_x2,
                "y1": weighted_average_y1,
                "y2": weighted_average_y2
            }
            return weighted_average_box
        else:
            print("Total weight is zero, cannot calculate weighted average.")
            return None


    # This function takes list of details of the same object from different movie scans
    # and aggregate this details. For ex. it takes list of average boxes location from 
    # different movies and calculate the average box.
    def _create_track_representation(self, object_sequence_details, flag_tracks_class):
        class_aggregated_data = { 'classes' : {} }
        sum_locations = {}
        total_boxes, total_frames, total_movement_rate = 0, 0, 0
        track_classes = []
        # Iterate over each object data dictionary
        for seq_one_scan_details in object_sequence_details:
            scan_name = seq_one_scan_details['scan_name']
            track_id = str(seq_one_scan_details['id'])

            if flag_tracks_class and (scan_name in flag_tracks_class) and \
             (flag_tracks_class[scan_name] and (track_id in flag_tracks_class[scan_name])):
                track_class = flag_tracks_class[scan_name][track_id]
                track_classes.append(track_class)
            
            box_location_avg = seq_one_scan_details['box_location_avg']
            classes_freq = seq_one_scan_details['classes_freq']

            # Sum the total number of boxes and frames
            total_boxes += seq_one_scan_details['boxes_count']
            total_frames += seq_one_scan_details['flag_frames_count']
            total_movement_rate += seq_one_scan_details['movement_rate']

            # Aggregate box locations
            for key, value in box_location_avg.items():
                sum_locations[key] = sum_locations.get(key, 0) + value

            # Iterate over each class in the current object data
            for class_name, class_data in classes_freq.items():
                # Aggregate the confidence and weight for the class
                if class_name in class_aggregated_data['classes']:
                    class_aggregated_data['classes'][class_name]['sum_confidence'] += class_data['conf'] * class_data['weight']
                    class_aggregated_data['classes'][class_name]['boxes_count'] += class_data['weight']
                else:
                    class_aggregated_data['classes'][class_name] = {
                        'sum_confidence': class_data['conf'] * class_data['weight'],
                        'boxes_count': class_data['weight']
                    }

        # Calculate the average confidence for each class
        for class_name, class_data in class_aggregated_data['classes'].items():
            sum_confidence = class_data['sum_confidence']
            class_boxes_count = class_data['boxes_count']
            
            class_data['class_percentage'] = class_boxes_count / total_boxes
            if class_boxes_count > 0:
                class_data['average_confidence'] = sum_confidence / class_boxes_count
            else:
                class_data['average_confidence'] = 0.0
            
            del class_data["sum_confidence"]
            del class_data["boxes_count"]


        # Calculate the average location for all boxes
        avg_location = {key: value / len(object_sequence_details) for key, value in sum_locations.items()}
        class_aggregated_data['average_location'] = avg_location
        class_aggregated_data['detection_ratio'] = total_boxes / total_frames if total_frames > 0 else 0.0
        class_aggregated_data['movement_rate'] = total_movement_rate / len(object_sequence_details) if len(object_sequence_details) > 0 else 0.0
        class_aggregated_data['track_classes'] = track_classes

        return class_aggregated_data


    def _read_classifications(self, classif_dir, scans_names, flag):
        return {
            scan_name: GeneralUtils._load_json(os.path.join(classif_dir, scan_name, f"{flag}.json"))
            for scan_name in scans_names
        }


    def _agregate_boxes_details(self, object_details):
        weighted_sum_x1 = weighted_sum_x2 = weighted_sum_y1 = weighted_sum_y2 = total_weight = 0
        classes_count = {}
        for item in object_details:
            # Calculate the weighted average of boxes
            weight = item['weight']
            total_weight += weight
            weighted_sum_x1 += item['box_location_avg']['x1'] * weight
            weighted_sum_x2 += item['box_location_avg']['x2'] * weight
            weighted_sum_y1 += item['box_location_avg']['y1'] * weight
            weighted_sum_y2 += item['box_location_avg']['y2'] * weight

            # Iterate through key-value pairs(class-count appearance) in the dictionary
            for key, value in item['classes_count'].items():
                # If the key is already in the result_dict, add the value to it
                if key in classes_count:
                    classes_count[key] += value
                # If the key is not in the result_dict, add the key-value pair to it
                else:
                    classes_count[key] = value


        if total_weight > 0:
            weighted_average_x1 = weighted_sum_x1 / total_weight
            weighted_average_x2 = weighted_sum_x2 / total_weight
            weighted_average_y1 = weighted_sum_y1 / total_weight
            weighted_average_y2 = weighted_sum_y2 / total_weight
            weighted_average_box = {
                "x1": weighted_average_x1,
                "x2": weighted_average_x2,
                "y1": weighted_average_y1,
                "y2": weighted_average_y2
            }

            return {
                'box_location': weighted_average_box,
                'classes_count': classes_count
            }
        else:
            print("Total weight is zero, cannot calculate weighted average.")
            return None
        

    def _report_flag_nests(self, scans_names, flag_dir, tracked_terns_jsons, objects_assosiation, \
                              video_converter_dir, classif_dir):
        flag = os.path.basename(flag_dir)
        # Create directory for flag results
        GeneralUtils.create_directory(flag_dir)
        # holds box location(by calculate the average) of every tracked object 
        object_sequences_details = [[] for _ in range(len(objects_assosiation))]  # Creates a list containing empty arrays

        # Create for the flag sequence of images with only brooder terns boxes 
        for index, tracked_terns_json in enumerate(tracked_terns_jsons):
            # Skip to the next tour file if the tour does not have the file
            if not os.path.exists(tracked_terns_json):
                continue
            
            with open(tracked_terns_json, "r") as json_file:
                tracked_objects_json = json.load(json_file)
                tracked_objects = [tracked_object for tracked_object in tracked_objects_json["object_boxes"] if len(tracked_object['predictions']) > 3]
                if len(tracked_objects) == 0:
                    continue
                
                images_dir = f'{video_converter_dir}/{scans_names[index]}'
                file_name = f'{scans_names[index].replace("/", "_")}.jpg'

                GeneralUtils.copy_image(images_dir, flag_dir, os.path.basename(tracked_objects[0]['predictions'][0]["image_path"]), file_name)

                for i, object_assosiation in enumerate(objects_assosiation):
                    if object_assosiation[index] == -1:
                        continue

                    tracked_object = tracked_objects[object_assosiation[index]]
                    # Boxes of assosiated breeding terns are colored on the same color
                    color = GeneralUtils.colors_with_names[i % len(GeneralUtils.colors_with_names)][1]
                    GeneralUtils.draw_boxes([tracked_object['predictions'][0]], f'{flag_dir}/{file_name}', color, i)

                    
                    # Intermediation aggregation of the tracked object boxes(only for the boxes from one scan)
                    object_sequences_details[i].append({
                        'scan_name': scans_names[index],
                        'id': tracked_object['id'],
                        'box_location_avg': self._calc_box_location_average(tracked_object['predictions']),
                        'classes_freq': self._aggregate_classes_freq(tracked_object['predictions']),
                        'boxes_count': len(tracked_object['predictions']),
                        'flag_frames_count': tracked_objects_json["frames_number"],
                        'movement_rate': tracked_object['iou'],
                    })

        # Read flag jsons of classifications
        flag_tracks_class = self._read_classifications(classif_dir, scans_names, flag)
        # print('flag: ', flag)
        # print('tracks number - ', len(object_sequences_details))
        tracks_details = []
        # Aggregate boxes of the same object from different movies 
        for object_sequence_details in object_sequences_details:
            track_details = self._create_track_representation(object_sequence_details, flag_tracks_class)
            tracks_details.append(track_details)

        flag_report_json = {
            'nests_details': tracks_details,
            'nests_total': len(objects_assosiation)
        }
        
        with open(f'{flag_dir}/report.json', 'w') as json_file:
            json.dump(flag_report_json, json_file, indent=4)
                

if __name__=='__main__':
    config = configparser.ConfigParser()
    # Read the config file
    config.read('track_breeding_terns.ini', encoding="utf8")
    # Access values from the config file
    video_converter_dir = config.get('General', 'video_converter_dir')
    one_scan_result_dir = config.get('General', 'one_scan_result_dir')
    mult_scans_result_dir = config.get('General', 'mult_scans_result_dir')
    classif_dir = config.get('General', 'classification_dir')

    # Extract tours list names from command-line arguments
    movies_names = sys.argv[1:]
        
    nested_terns_tracker = NestedTernsTracker()
    nested_terns_tracker.track_breeding_terns(movies_names, one_scan_result_dir, mult_scans_result_dir, 
                                            video_converter_dir, classif_dir)
    

    
    