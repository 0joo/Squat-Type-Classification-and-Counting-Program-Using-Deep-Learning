import cv2
import math
import joblib
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

class Regressor(nn.Module):
    def __init__(self):
        super().__init__()
        self.fc1 = nn.Linear(16, 8)
        self.fc2 = nn.Linear(8, 4)
        
    def forward(self, x):
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        return x

colors_list = [(207,203,201),(235,162,54),(86,205,255),(132,99,255)]
squat_list = [ "none", "quarter squat", "half squat", "full squat"]

CTX = torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu')
savePath = "/submission_1024.pth" #스쿼트 판별 모델 경로
model = Regressor().to(CTX)
model.load_state_dict(torch.load(savePath))
model.eval()

class Countpose:
    __squat_cnt = 0
    __squat = "none"
    __total_squat = [0, 0, 0] #총 횟수 저장

    def __init__(self):
        self.__direction = "none"
        self.__coords = [] #s,h,k,a/l,r순서대로
        self.__cur_squat = "none"
        self.__cur_angle = 0

    # 왼쪽/오른쪽 구분 좌표 저장
    def get_pose_coord(self, new_csv_row): 
        self.eval_direction(new_csv_row)
        if(self.__direction == "left"):
            for i in [0,4,8,12]: #left index
                self.__coords.extend([new_csv_row[i], new_csv_row[i+1]])
        else:
            for i in [2,6,10,14]: #right index
                self.__coords.extend([new_csv_row[i], new_csv_row[i+1]])
        
        length = math.sqrt((self.__coords[4]-self.__coords[6])**2 +
         (self.__coords[5]-self.__coords[7])**2)
        up = int(length*0.1)
        self.__coords[5] -= up

    def eval_direction(self, new_csv_row):
        left_ankle = new_csv_row[12:14]
        right_ankle = new_csv_row[14:16]
        # 발목을 기준으로 왼/오 구분
        if left_ankle[1]<right_ankle[1]:
            self.__direction = "right"
        else:
            self.__direction = "left"

    def draw_skeleton(self, frame_width, frame_height, new_csv_row, image_debug):
        self.cal_cur_squat(frame_width, frame_height, new_csv_row)
        #draw circle at point
        for i in [0,2,4,6]:
            cv2.circle(image_debug,(self.__coords[i],self.__coords[i+1]),4,(145,194,74),2)
        #draw line
        color = colors_list[squat_list.index(self.__cur_squat)]
        for i in [0,2,4]:
            cv2.line(image_debug, (self.__coords[i], self.__coords[i+1]),(self.__coords[i+2], self.__coords[i+3]), color, 3)

    def cal_cur_squat(self, frame_width, frame_height, new_csv_row):
        # normalized
        n_coord = []
        for i, coord in enumerate(new_csv_row):
            if i%2 == 0:
                #x
                n_coord.append((2/frame_width) * coord - 1)
            else:
                #y
                n_coord.append((-2/frame_height) * coord + 1)

        test = torch.tensor(n_coord).float().to(CTX)
        
        # out features 4
        output = model(test)
        prediction = int(torch.max(output.data, 0)[1].cpu().numpy())
        self.__cur_squat = squat_list[prediction]

    def check_for_real_time(self, x1, x2, y1, y2):
        shoulderx = self.__coords[0]
        shouldery = self.__coords[1]
        anklex = self.__coords[6]
        ankley = self.__coords[7]
        
        if(x1<anklex<x2 and y1<ankley<y2 and x1<shoulderx<x2 and y1<shouldery<y2):
            return 2 #stand in right place
        else:
            return 1      

    @property
    def squat(self):
        return Countpose.__squat

    @squat.setter
    def squat(self, input_squat):
        Countpose.__squat = input_squat

    @property
    def cur_squat_index(self):
        return squat_list.index(self.__cur_squat)

    @property
    def squat_cnt(self):
        return Countpose.__squat_cnt 

    @property
    def total_squat(self):
        return self.__total_squat      
    
    @classmethod
    def plus_count(cls):
        cls.__squat_cnt += 1 #static 변수

    @classmethod
    def set_total_squat(cls):
        cls.__total_squat[squat_list.index(cls.squat)-1] += 1


def get_max_squat(pre_point, cur_point):
    pre_squat = pre_point.cur_squat_index
    cur_squat = cur_point.cur_squat_index
    
    if cur_squat == pre_squat:
        return

    if cur_squat > pre_squat:
        Countpose.squat = squat_list[cur_squat]
    elif cur_point.cur_squat_index == 0 :
        Countpose.plus_count()
        Countpose.set_total_squat()