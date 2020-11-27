from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import argparse
import csv
import os
import shutil

from PIL import Image as PImage
import torch
import torch.nn.parallel
import torch.backends.cudnn as cudnn
import torch.optim
import torch.utils.data
import torch.utils.data.distributed
import torchvision.transforms as transforms
import torchvision
import cv2
import numpy as np

import sys
sys.path.append("../lib")
sys.path.append("../tools")
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

import tools._init_paths
import time
import models
from config import cfg
from config import update_config
from core.inference import get_final_preds
from utils.transforms import get_affine_transform

CTX = torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu')

from Countpose_deep import *
import copy

from tkinter import *
from PIL import ImageTk, Image, ImageFont, ImageDraw
from tkinter.filedialog import askopenfilename
from tkinter import ttk

import torch.nn as nn
import torch.nn.functional as F

import pickle
import joblib

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
import db
from datetime import datetime

COCO_KEYPOINT_INDEXES = {
    0: 'nose',
    1: 'left_eye',
    2: 'right_eye',
    3: 'left_ear',
    4: 'right_ear',
    5: 'left_shoulder',
    6: 'right_shoulder',
    7: 'left_elbow',
    8: 'right_elbow',
    9: 'left_wrist',
    10: 'right_wrist',
    11: 'left_hip',
    12: 'right_hip',
    13: 'left_knee',
    14: 'right_knee',
    15: 'left_ankle',
    16: 'right_ankle'
}

COCO_INSTANCE_CATEGORY_NAMES = [
    '__background__', 'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus',
    'train', 'truck', 'boat', 'traffic light', 'fire hydrant', 'N/A', 'stop sign',
    'parking meter', 'bench', 'bird', 'cat', 'dog', 'horse', 'sheep', 'cow',
    'elephant', 'bear', 'zebra', 'giraffe', 'N/A', 'backpack', 'umbrella', 'N/A', 'N/A',
    'handbag', 'tie', 'suitcase', 'frisbee', 'skis', 'snowboard', 'sports ball',
    'kite', 'baseball bat', 'baseball glove', 'skateboard', 'surfboard', 'tennis racket',
    'bottle', 'N/A', 'wine glass', 'cup', 'fork', 'knife', 'spoon', 'bowl',
    'banana', 'apple', 'sandwich', 'orange', 'broccoli', 'carrot', 'hot dog', 'pizza',
    'donut', 'cake', 'chair', 'couch', 'potted plant', 'bed', 'N/A', 'dining table',
    'N/A', 'N/A', 'toilet', 'N/A', 'tv', 'laptop', 'mouse', 'remote', 'keyboard', 'cell phone',
    'microwave', 'oven', 'toaster', 'sink', 'refrigerator', 'N/A', 'book',
    'clock', 'vase', 'scissors', 'teddy bear', 'hair drier', 'toothbrush'
]

csv_headers = [
        'left_shoulder_x', 'left_shoulder_y',
        'right_shoulder_x', 'right_shoulder_y',
        'left_hip_x', 'left_hip_y',
        'right_hip_x', 'right_hip_y',
        'left_knee_x', 'left_knee_y',
        'right_knee_x', 'right_knee_y',
        'left_ankle_x', 'left_ankle_y',
        'right_ankle_x', 'right_ankle_y',
        'squat'
    ]

def get_person_detection_boxes(model, img, threshold=0.5):
    pil_image = PImage.fromarray(img)  # Load the image #formarray???
    transform = transforms.Compose([transforms.ToTensor()])  # Defing PyTorch Transform
    transformed_img = transform(pil_image)  # Apply the transform to the image
    pred = model([transformed_img.to(CTX)])  # Pass the image to the model
    # Use the first detected person
    pred_classes = [COCO_INSTANCE_CATEGORY_NAMES[i]
                    for i in list(pred[0]['labels'].cpu().numpy())]  # Get the Prediction Score
    pred_boxes = [[(i[0], i[1]), (i[2], i[3])]
                  for i in list(pred[0]['boxes'].cpu().detach().numpy())]  # Bounding boxes
    pred_scores = list(pred[0]['scores'].cpu().detach().numpy())
    person_boxes = []
    # Select box has score larger than threshold and is person
    for pred_class, pred_box, pred_score in zip(pred_classes, pred_boxes, pred_scores):
        if (pred_score > threshold) and (pred_class == 'person'):
            person_boxes.append(pred_box)

    return person_boxes


def get_pose_estimation_prediction(pose_model, image, centers, scales, transform):
    rotation = 0
    # pose estimation transformation
    model_inputs = []
    for center, scale in zip(centers, scales):
        trans = get_affine_transform(center, scale, rotation, cfg.MODEL.IMAGE_SIZE)
        # Crop smaller image of people
        model_input = cv2.warpAffine(
            image,
            trans,
            (int(cfg.MODEL.IMAGE_SIZE[0]), int(cfg.MODEL.IMAGE_SIZE[1])),
            flags=cv2.INTER_LINEAR)
        # hwc -> 1chw
        model_input = transform(model_input)#.unsqueeze(0)
        model_inputs.append(model_input)
    # n * 1chw -> nchw
    model_inputs = torch.stack(model_inputs)
    # compute output heatmap
    output = pose_model(model_inputs.to(CTX))
    coords, _ = get_final_preds(
        cfg,
        output.cpu().detach().numpy(),
        np.asarray(centers),
        np.asarray(scales))

    return coords


def box_to_center_scale(box, model_image_width, model_image_height):
    center = np.zeros((2), dtype=np.float32)
    bottom_left_corner = box[0]
    top_right_corner = box[1]
    box_width = top_right_corner[0]-bottom_left_corner[0]
    box_height = top_right_corner[1]-bottom_left_corner[1]
    bottom_left_x = bottom_left_corner[0]
    bottom_left_y = bottom_left_corner[1]
    center[0] = bottom_left_x + box_width * 0.5
    center[1] = bottom_left_y + box_height * 0.5
    aspect_ratio = model_image_width * 1.0 / model_image_height
    pixel_std = 200
    if box_width > aspect_ratio * box_height:
        box_height = box_width * 1.0 / aspect_ratio
    elif box_width < aspect_ratio * box_height:
        box_width = box_height * aspect_ratio
    scale = np.array(
        [box_width * 1.0 / pixel_std, box_height * 1.0 / pixel_std],
        dtype=np.float32)
    if center[0] != -1:
        scale = scale * 1.25

    return center, scale


def prepare_output_dirs(prefix='/output/'):
    pose_dir = os.path.join(prefix, "pose")
    if os.path.exists(pose_dir) and os.path.isdir(pose_dir):
        shutil.rmtree(pose_dir)
    os.makedirs(pose_dir, exist_ok=True)

    return pose_dir


def parse_args():
    parser = argparse.ArgumentParser(description='Train keypoints network')
    parser.add_argument('opts',
                        help='Modify config options using the command-line',
                        default=None,
                        nargs=argparse.REMAINDER)

    args = parser.parse_args()
    args.modelDir = ''
    args.logDir = ''
    args.dataDir = ''
    args.prevModelDir = ''
    args.cfg = '/inference-config.yaml'#경로
    args.writeBoxFrames = True
    args.outputDir =  "output"
    args.inferenceFps = 10
    return args

def start_squat(vid, userNo):
    # transformation
    pose_transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406],
                            std=[0.229, 0.224, 0.225]),
    ])

    # cudnn related setting
    cudnn.benchmark = cfg.CUDNN.BENCHMARK
    torch.backends.cudnn.deterministic = cfg.CUDNN.DETERMINISTIC
    torch.backends.cudnn.enabled = cfg.CUDNN.ENABLED

    args = parse_args()
    update_config(cfg, args)
    pose_dir = prepare_output_dirs(args.outputDir)
    csv_output_rows = []

    box_model = torchvision.models.detection.fasterrcnn_resnet50_fpn(pretrained=True)
    box_model.to(CTX)
    box_model.eval()
    pose_model = eval('models.'+cfg.MODEL.NAME+'.get_pose_net')(
        cfg, is_train=False
    )

    pose_model.load_state_dict(torch.load("/pose_hrnet_w32_256x192.pth"), strict=False) #경로
    pose_model.to(CTX)
    pose_model.eval()

    # Loading an video
    #1 -> webcam / 2->video
    if(vid==1):
        vidcap = cv2.VideoCapture(0)
    else:
        vidcap = openImage()
    
    fps = vidcap.get(cv2.CAP_PROP_FPS)
    if fps < args.inferenceFps:
        print('desired inference fps is '+str(args.inferenceFps)+' but video fps is '+str(fps))
        exit()
    skip_frame_cnt = round(fps / args.inferenceFps)
    frame_width = int(vidcap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(vidcap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    #file 이름 현시간으로 저장
    timestr = time.strftime("%Y%m%d-%H%M%S")
    outcap = cv2.VideoWriter('{}/pose_{}.avi'.format(args.outputDir, timestr), 
                cv2.VideoWriter_fourcc('M','J','P','G'), int(skip_frame_cnt), (frame_width, frame_height))

    pre_center = 0
    count = 0
    pre_point = Countpose()
    while vidcap.isOpened():
        total_now = time.time()
        ret, image_bgr = vidcap.read()
        count += 1
        
        if (count !=0 and not ret):   #종료조건
            print('Squat Finish!')
            break

        if not ret:
            continue

        if count % skip_frame_cnt != 0:
            continue

        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)

        #스쿼트 판별 회전
        # ffmpeg -i image_bgr
        if(vid==3):
            rows,cols = image_rgb.shape[:2]
            M = cv2.getRotationMatrix2D((cols/2,rows/2),270, rows/cols) #왼쪽으로 90도 회전
            image_rgb = cv2.warpAffine(image_rgb,M,(cols,rows))

        # Clone 2 image for person detection and pose estimation
        if cfg.DATASET.COLOR_RGB:
            image_per = image_rgb.copy()
            image_pose = image_rgb.copy()
        else:
            image_per = image_bgr.copy()
            image_pose = image_bgr.copy()

        # Clone 1 image for debugging purpose
        image_debug = image_bgr.copy()

        #영상 회전
        if(vid==3):
            rows,cols = image_debug.shape[:2]
            M = cv2.getRotationMatrix2D((cols/2,rows/2),270, rows/cols) #왼쪽으로 90도 회전
            image_debug = cv2.warpAffine(image_debug,M,(cols,rows))

        # object detection box
        now = time.time() 

        # cuda out of memory?
        pred_boxes = get_person_detection_boxes(box_model, image_per, threshold=0.9)
        then = time.time()
        print("Find person bbox in: {} sec".format(then - now))

        # Can not find people. Move to next frame
        if not pred_boxes:
            count += 1
            continue

        if args.writeBoxFrames:
            for box in pred_boxes:
                cv2.rectangle(image_debug, box[0], box[1], color=(145, 194, 74),
                            thickness=3)  # Draw Rectangle with the coordinates

        # pose estimation : for multiple people
        centers = []
        scales = []
        for box in pred_boxes:
            center, scale = box_to_center_scale(box, cfg.MODEL.IMAGE_SIZE[0], cfg.MODEL.IMAGE_SIZE[1])
            centers.append(center)
            scales.append(scale)

        now = time.time()
        pose_preds = get_pose_estimation_prediction(pose_model, image_pose, centers, scales, transform=pose_transform)
        then = time.time()
        print("Find person pose in: {} sec".format(then - now))

        new_csv_row = []
        for coords in pose_preds:
            # Draw each point on image
            for i, coord in enumerate(coords):
                if i < 5 or 6 < i < 11 :
                    continue
                x_coord, y_coord = int(coord[0]), int(coord[1])
                cv2.circle(image_debug, (x_coord, y_coord), 4, (145, 194, 74), 2)
                new_csv_row.extend([x_coord, y_coord])
        
        # 두 명 이상이면 pass
        if(len(new_csv_row)) > 16:
            continue
        
        # squat
        # 스쿼트 판정해서 올라왔을때 횟수, 스쿼트 표시
        cur_point = Countpose()
        cur_point.get_pose_coord(new_csv_row)
        cur_point.draw_skeleton(frame_width, frame_height, new_csv_row, image_debug)
        check = vid

        if(vid==1):
            #위치 기준
            x1 = int(frame_width/2 - frame_width * 0.25)
            y1 = int(frame_height * 0.06)
            x2 = int(frame_width/2 + frame_width * 0.25)
            y2 = int(frame_height - frame_height * 0.03)

            check = cur_point.check_for_real_time(x1, x2, y1, y2)
        
        if(check==2 or check==3):
            get_max_squat(pre_point, cur_point)
            pre_point = copy.deepcopy(cur_point) #맨 마지막에

        else:
            cv2.putText(image_debug, "Please stand in blue box", (10,50), cv2.FONT_HERSHEY_SIMPLEX,1, (255, 0, 0), 2)
            rec_init = cv2.rectangle(image_debug, (x1, y1), (x2, y2), (255, 0, 0), 3)

        squat = cur_point.squat
        squat_cnt = "count = {:3d}".format(cur_point.squat_cnt)

        # 폰트
        fontpath = "/font/ITCKRIST.TTF" #폰트경로
        myfont = ImageFont.truetype(font = fontpath, size = 50)
        img_pil = Image.fromarray(image_debug)
        draw = ImageDraw.Draw(img_pil)
        draw.text((100,100), squat , fill = (0,255,255) , font = myfont)
        draw.text((100,150), squat_cnt , fill = (0,255,255) , font = myfont)
        image_debug = np.array(img_pil)

        total_then = time.time()
        
        cv2.imshow("pos", image_debug)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

        new_csv_row.append(cur_point.cur_squat_index)
        csv_output_rows.append(new_csv_row)
        img_file = os.path.join(pose_dir, 'pose_{:08d}.jpg'.format(count))
        cv2.imwrite(img_file, image_debug)
        outcap.write(image_debug)

    # write csv
    csv_output_filename = os.path.join(args.outputDir, 'pose-data.csv')
    with open(csv_output_filename, 'w', newline='') as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerow(csv_headers)
        csvwriter.writerows(csv_output_rows)

    vidcap.release()
    outcap.release()
    cv2.destroyAllWindows()

    # 결과 저장
    total_squat = cur_point.total_squat
    db.squat_add(userNo, total_squat[0], total_squat[1], total_squat[2], cur_point.squat_cnt)

#button
def btn():
    if(radVar.get()==1):
        print("cam")
        result = 1
        
    elif(radVar.get()==2):
        print("video")
        result = 2

    else:
        print("something wrong")
        return None

    return result

def openImage():
    fullfilename = askopenfilename(initialdir="/", #폴더경로
    title="Select a file", filetypes=[("Video files", "*.avi *.mp4 *.f4v *.flv *.m4v *.mkv *.mov *.3gp *.mpeg *.mpg *.mts *.ts *.vob *.webm *.wmv *.gif"), ("All Files","*.*")])

    if not fullfilename:
        return openImage()
    vidcap = cv2.VideoCapture(fullfilename)
    return vidcap

def close():
    root.destroy()

# for flask
def start(num, userNo):
    root =Tk()
    # 웹페이지에서 이용시 주석 처리
    # root.title("webcam/video")
    # root.geometry("250x100+700+10")
    # radVar=IntVar()
    # webcam = Radiobutton(root, text = "  webcam", value = 1, variable = radVar)
    # video = Radiobutton(root, text = "  video", value = 2, variable = radVar)
    # start = Button(root, text = "start", overrelief="solid", width = 13, command = close)
    # webcam.place(x = 30, y = 30)
    # video.place(x = 140, y = 30)
    # start.place(x = 130, y = 70)
    # root.mainloop()
    # vid = btn()
    root.withdraw()

    vid = num # 1 웹캠, 2 비디오(가로), 3 비디오(세로)
    if vid != None:
        start_squat(vid, userNo)
    root.destroy()
    return

if __name__ == "__main__":
    start(2, 1)