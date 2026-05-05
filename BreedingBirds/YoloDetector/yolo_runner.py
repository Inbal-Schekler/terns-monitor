import os
import re
import sys
import glob
import json
import shutil
import argparse
import configparser
from PIL import Image
from ultralytics import YOLO


script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, os.pardir, os.pardir))
# Add the project root to the Python path
sys.path.append(project_root)
from Utilities.global_utils import GeneralUtils


parser = argparse.ArgumentParser()

parser.add_argument('-r', '--images_dir_name', help='Directory name where the JPG images are located')
# Read the directory path where images located
images_dir_name = parser.parse_args().images_dir_name

config = configparser.ConfigParser()
# Read the config file
config.read('yolo_runner.ini', encoding="utf8")
# Directory path where the yolo result will be located
images_dir_path = config.get('General', 'images_dir')
# Directory path where the yolo result will be located
result_dirs_path = config.get('General', 'result_dir')
# number of images to run on YOLO model in each iteration
images_chunk_size = int(config.get('General', 'images_chunk_size'))
# YOLO model path 
yolo_model_path = config.get('General', 'yolo_model')

# Path directory where the images are located
images_dir_path = f'{images_dir_path}/{images_dir_name}'
# Path directory where the results will be located
results_dir_path = f'{result_dirs_path}/{images_dir_name}'

# Create directory for results
dir_utils = GeneralUtils()
dir_utils.create_directory(results_dir_path)
# Directories paths for the jsons and Images(with detection)
yolo_jsons_directory = f'{results_dir_path}/Jsons'
yolo_images_directory = f'{results_dir_path}/Images'
# Create dirs for jsons and images
os.makedirs(yolo_jsons_directory, exist_ok=True)
os.makedirs(yolo_images_directory, exist_ok=True)

# Retrieve all JPG image file paths in the directory
images_list = glob.glob(os.path.join(images_dir_path, "*.jpg"))
images_list = sorted(images_list, key=dir_utils.extract_flag_and_image_numbers)

# Filter out corrupted images that PIL cannot open
from PIL import Image as PILImage
valid_images = []
for img_path in images_list:
    try:
        PILImage.open(img_path).verify()
        valid_images.append(img_path)
    except Exception:
        print(f"Skipping corrupted image: {os.path.basename(img_path)}")
images_list = valid_images

# Load a model
model = YOLO(yolo_model_path)

images_chunk_size = 16

for start in range(0, len(images_list), images_chunk_size):
    
    end = start + images_chunk_size
    
    images_chunk = images_list[start:end]
    
    # predict images chunk in YOLO model
    results = model(images_chunk, show_conf=False, save=False, line_width=2, show_labels=False)
    for r, original_path in zip(results, images_chunk):
        file_name = os.path.splitext(os.path.basename(original_path))[0]
        boxes = json.loads(r.to_json())
        json_result = {
            'predictions': boxes,
            'path': original_path
        }

        with open(yolo_jsons_directory + "/" + file_name + ".json", "w") as file:
            json.dump(json_result, file)

        # Save annotated image with the correct flag-based filename
        annotated = r.plot()  # returns BGR numpy array
        PILImage.fromarray(annotated[:, :, ::-1]).save(
            yolo_images_directory + "/" + file_name + ".jpg"
        )