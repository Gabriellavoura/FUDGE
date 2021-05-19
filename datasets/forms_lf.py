import torch.utils.data
import numpy as np
import json
#from skimage import io
#from skimage import draw
#import skimage.transform as sktransform
import os
import math
#from utils.crop_transform import CropTransform
from utils import augmentation
from collections import defaultdict
import timeit

import utils.img_f as img_f

IAIN_CATCH=['193','194','197','200']
ONE_DONE=[]

def flipPoints(points):
    newPoints = list(reversed(points))
    for i in range(len(newPoints)):
        newPoints[i] = torch.Tensor([[newPoints[i][0,1],newPoints[i][0,0]],[newPoints[i][1,1],newPoints[i][1,0]]])
    return newPoint

class FormsLF(torch.utils.data.Dataset):
    """
    Class for reading forms dataset and creating starting and ending gt
    """


    def __init__(self, dirPath=None, split=None, config=None, lines=None):
        #if 'augmentation_params' in config['data_loader']:
        #    self.augmentation_params=config['augmentation_params']
        #else:
        #    self.augmentation_params=None
        if 'cache_resized_lines' in config:
            self.cache_resized = config['cache_resized_lines']
            self.cache_path = os.path.join(dirPath,'cache_'+str(self.rescale_range[1]))
            if self.cache_resized and not os.path.exists(self.cache_path):
                os.mkdir(self.cache_path)
        else:
            self.cache_resized = False
        if 'only_types' in config:
            self.only_types = config['only_types']
        else:
            self.only_types=None
        if 'swap_circle' in config:
            self.swapCircle = config['swap_circle']
        else:
            self.swapCircle = True
        if 'no_blanks' in config:
            self.no_blanks = config['no_blanks']
        else:
            self.no_blanks = False
        if 'no_print_fields' in config:
            self.no_print_fields = config['no_print_fields']
        else:
            self.no_print_fields = False
        if 'augment' in config:
            self.augment = config['augment']
        else:
            self.augment = False

        if 'detection_dir' in config:
            self.detection_dir = config['detection_dir']
        else:
            self.detection_dir = None

        if lines is not None:
            self.lines=lines
        else:
            with open(os.path.join(dirPath,'train_valid_test_split.json')) as f:
                #if split=='valid' or split=='validation':
                #    trainTest='train'
                #else:
                #    trainTest=split
                groupsToUse = json.loads(f.read())[split]
            self.lines=[]
            for groupName, imageNames in groupsToUse.items():
                #print('{} {}'.format(groupName, imageNames))
                oneonly=False
                if groupName in IAIN_CATCH:
                    if groupName in ONE_DONE:
                        oneonly=True
                        with open(os.path.join(dirPath,'groups',groupName,'template'+groupName+'.json')) as f:
                            T_annotations = json.loads(f.read())
                    else:
                        print('Skipped group {} as Iain has incomplete GT here'.format(groupName))
                        continue
                for imageName in imageNames:
                    imageName_npy = imageName[0:imageName.rfind('.')]+'.npy'
                    
                    if oneonly and T_annotations['imageFilename']!=imageName:
                        #print('skipped {} {}'.format(imageName,groupName))
                        continue
                    elif oneonly:
                        print('only {} from {}'.format(imageName,groupName))
                    org_path = os.path.join(dirPath,'groups',groupName,imageName)
                    if self.cache_resized:
                        path = os.path.join(self.cache_path,imageName)
                    else:
                        path = org_path
                    jsonPath = org_path[:org_path.rfind('.')]+'.json'
                    #print(jsonPath)
                    if os.path.exists(jsonPath):
                        with open(jsonPath) as f:
                            annotations = json.loads(f.read())
                        rescale=1.0
                        if self.cache_resized and not os.path.exists(path):
                            org_img = img_f.imread(org_path)
                            target_dim1 = self.rescale_range[1]
                            target_dim0 = int(org_img.shape[0]/float(org_img.shape[1]) * target_dim1)
                            resized = img_f.resize(org_img,(target_dim1, target_dim0))
                            img_f.imwrite(path,resized)
                            rescale = target_dim1/float(org_img.shape[1])
                        elif self.cache_resized:
                            imW = annotations['width']

                            #target_dim1 = self.rescale_range[1]
                            #rescale = target_dim1/float(imW)

                        if 'text' in self.only_types:
                            textLines = self.getLines(annotations['textBBs'],rescale)
                            for l,forwards in textLines:
                                if self.detection_dir is not None:
                                    if forwards:
                                        detPath = os.path.join(self.detection_dir,'text_end_gt',imageName_npy) #not ground truth, just folder name
                                    else:
                                        detPath = os.path.join(self.detection_dir,'text_start_gt',imageName_npy)
                                else:
                                    detPath = None
                                self.lines.append({'imagePath':path, 'rescaled':rescale, 'points':l, 'steps':getNumSteps(l), 'forwards':forwards, 'detectionPath':detPath})
                        if 'field' in self.only_types:
                            fieldLines = self.getLines(annotations['fieldBBs'],rescale,True)
                            for l,forwards in fieldLines:
                                if self.detection_dir is not None:
                                    if forwards:
                                        detPath = os.path.join(self.detection_dir,'field_end_gt',imageName_npy)
                                    else:
                                        detPath = os.path.join(self.detection_dir,'field_start_gt',imageName_npy)
                                else:
                                    detPath = None
                                self.lines.append({'imagePath':path, 'rescaled':rescale, 'points':l, 'steps':getNumSteps(l), 'forwards':forwards, 'detectionPath':detPath})
                        if 'horz' in self.only_types or 'horzLinks' in self.only_types:
                            annotations['byId']={}
                            for bb in annotations['fieldBBs']:
                                annotations['byId'][bb['id']]=bb
                            for bb in annotations['textBBs']:
                                annotations['byId'][bb['id']]=bb
                            horzLines = self.getHorzLines(annotations,rescale)
                            for l,forwards in horzLines:
                                if self.detection_dir is not None:
                                    if forwards:
                                        detPath = os.path.join(self.detection_dir,'end?',imageName)
                                    else:
                                        detPath = os.path.join(self.detection_dir,'start?',imageName)
                                else:
                                    detPath = None
                                self.lines.append({'imagePath':path, 'rescaled':rescale, 'points':l, 'steps':getNumSteps(l), 'forwards':forwards, 'detectionDir':det_dir})


        
        



    def __len__(self):
        return len(self.lines)

    def __getitem__(self,index):
        ##ticFull=timeit.default_timer()
        imagePath = self.lines[index]['imagePath']
        detectionPath = self.lines[index]['detectionPath']
        #print(imagePath)
        points = self.lines[index]['points']
        steps = self.lines[index]['steps']
        rescaled = self.lines[index]['rescaled']
        forwards = self.lines[index]['forwards']

        ##tic=timeit.default_timer()
        img = img_f.imread(imagePath)#/255.0
        ##print('imread: {}  [{}, {}]'.format(timeit.default_timer()-tic,org_img.shape[0],org_img.shape[1]))

        #target_dim1 = int(np.random.uniform(self.rescale_range[0], self.rescale_range[1]))
        #s = target_dim1 / float(org_img.shape[1])
        #s *= rescaled
        #print(s)
        #target_dim0 = int(org_img.shape[0]/float(org_img.shape[1]) * target_dim1)
        ##tic=timeit.default_timer()
        #org_img = img_f.resize(org_img,(target_dim1, target_dim0))
        ##print('resize: {}  [{}, {}]'.format(timeit.default_timer()-tic,org_img.shape[0],org_img.shape[1]))
        

        if self.augment:

            ##tic=timeit.default_timer()
            img = augmentation.apply_random_color_rotation(img)
            img = augmentation.apply_tensmeyer_brightness(img)
            ##print('augmentation: {}'.format(timeit.default_timer()-tic))
        pointsAngle=[]
        for p in points:
            x0 = p[0,1]
            x1 = p[0,0]
            y0 = p[1,1]
            y1 = p[1,0]
            dx = x0-x1
            dy = y0-y1
            d = math.sqrt(dx**2 + dy**2)
            mx = (x0+x1)/2.0
            my = (y0+y1)/2.0
            #Not sure if this is right...
            theta = -math.atan2(dx, -dy)
            pointsAngle.append(torch.Tensor([mx, my, theta, d/2, 1.0]))
        
        

        img = 1.0 - img / 128.0 #ideally the median value would be 0
        if detectionPath is not None:
            detection_res = np.load(detectionPath) #matrix of [instances, features] feautres:conf,x,y,rot,scale
        img = img.transpose([2,0,1]) #from [row,col,color] to [color,row,col]
        img = img.astype(np.float32)
        img = torch.from_numpy(img)
        
        #return {
        #        'img':img,
        #        'lf_xyrs':pointsAngle,
        #        'lf_xyxy':points
        #       }
        return img, points, pointsAngle, steps, forwards, detection_res




    def getLines(self,bbs,rescale,fields=False):
        s=rescale
        points=[]
        for bb in bbs:
            if ( fields and (
                    (self.no_blanks and (bb['isBlank']=='blank' or bb['isBlank']==3)) or
                    (self.no_print_fields and (bb['isBlank']=='print' or bb['isBlank']==2)) or
                    bb['type'] == 'fieldRow' or
                    bb['type'] == 'fieldCol' or
                    bb['type'] == 'fieldRegion' )):
                continue
            tX,tY,bX,bY,etX,etY,ebX,ebY = getRectPoints(bb['poly_points'])


            points.append( ([ torch.Tensor([[tX*s,bX*s],[tY*s,bY*s]]),
                              torch.Tensor([[etX*s,ebX*s],[etY*s,ebY*s]]) ], True) )
            points.append( ([ torch.Tensor([[ebX*s,etX*s],[ebY*s,etY*s]]),
                              torch.Tensor([[bX*s,tX*s],[bY*s,tY*s]]) ], False) )

        return points

    def getHorzLines(self,ann,rescale):
        s=rescale
        points=[]
        idsInHorz=set()
        for hLink in ann['horzLinks']:
            pointsTop=[]
            pointsBot=[]
            linePoints=[]
            rot=None
            for bbId in hLink:
                idsInHorz.add(bbId)
                bbSlanty=ann['byId'][bbId]['poly_points']
                tX,tY,bX,bY,etX,etY,ebX,ebY = getRectPoints(bbSlanty)
                bb = [ [tX,tY], [etX,etY], [ebX,ebY], [bX,bY] ]
                if rot is None:
                    rot=getRotation(bb)
                    #print(rot)
                #print(bb)

                if (len(pointsTop)==0 or
                        (rot=='left-right' and bb[0][0]>pointsTop[-1][0]) or
                        (rot=='right-left' and bb[0][0]<pointsTop[-1][0]) or
                        (rot=='up' and bb[0][1]<pointsTop[-1][1]) or
                        (rot=='down' and bb[0][1]>pointsTop[-1][1]) ):
                    pointsTop.append(bb[0])
                else:
                    pointsTop[-1]=( (pointsTop[-1][0]+bb[0][0])/2.0, (pointsTop[-1][1]+bb[0][1])/2.0 )
                #pointsTop.append(bb[0:2])
                pointsTop.append(bb[1])

                if len(pointsBot)==0 or (
                        (rot=='left-right' and bb[3][0]>pointsBot[-1][0]) or
                        (rot=='right-left' and bb[3][0]<pointsBot[-1][0]) or
                        (rot=='up' and bb[3][1]<pointsBot[-1][1]) or
                        (rot=='down' and bb[3][1]>pointsBot[-1][1]) ):
                    pointsBot.append(bb[3])
                else:
                    pointsBot[-1]=( (pointsBot[-1][0]+bb[3][0])/2.0, (pointsBot[-1][1]+bb[3][1])/2.0 )
                #pointsBot.append(bb[6:8])
                pointsBot.append(bb[2])
            for i in range(len(pointsTop)):
                linePoints.append( torch.Tensor([[pointsTop[i][0]*s,pointsBot[i][0]*s],[pointsTop[i][1]*s,pointsBot[i][1]*s]]) )
            points.append( (linePoints,True) )
            points.append( (flipPoints(linePoints),False) )

        #now everything not in a horz link
        for bbId in ann['byId'].keys()-idsInHorz:
            bb=ann['byId'][bbId]
            if ( bbId[0]=='f' and (
                    (self.no_blanks and (bb['isBlank']=='blank' or bb['isBlank']==3)) or
                    (self.no_print_fields and (bb['isBlank']=='print' or bb['isBlank']==2)) or
                    bb['type'] == 'fieldRow' or
                    bb['type'] == 'fieldCol' or
                    bb['type'] == 'fieldRegion' )):
                continue
            bbSlanty=bb['poly_points']
            tX,tY,bX,bY,etX,etY,ebX,ebY = getRectPoints(bbSlanty)
            points.append( ([ torch.Tensor([[tX*s,bX*s],[tY*s,bY*s]]),
                              torch.Tensor([[etX*s,ebX*s],[etY*s,ebY*s]]) ],True) )
            points.append( ([ torch.Tensor([[ebX*s,etX*s],[ebY*s,etY*s]]),
                              torch.Tensor([[bX*s,tX*s],[bY*s,tY*s]]) ], False) )
        return points

def getRectPoints(poly_points):               
    tlX = poly_points[0][0]
    tlY = poly_points[0][1]
    trX = poly_points[1][0]
    trY = poly_points[1][1]
    brX = poly_points[2][0]
    brY = poly_points[2][1]
    blX = poly_points[3][0]
    blY = poly_points[3][1]

    lX = (tlX+blX)/2.0
    lY = (tlY+blY)/2.0
    rX = (trX+brX)/2.0
    rY = (trY+brY)/2.0
    d=math.sqrt((lX-rX)**2 + (lY-rY)**2)

    hl = ((tlX-lX)*-(rY-lY) + (tlY-lY)*(rX-lX))/d #projection of half-left edge onto transpose horz run
    hr = ((brX-rX)*-(lY-rY) + (brY-rY)*(lX-rX))/d #projection of half-right edge onto transpose horz run
    h = (hl+hr)/2.0

    tX = lX + h*-(rY-lY)/d
    tY = lY + h*(rX-lX)/d
    bX = lX - h*-(rY-lY)/d
    bY = lY - h*(rX-lX)/d

    etX =tX + rX-lX
    etY =tY + rY-lY
    ebX =bX + rX-lX
    ebY =bY + rY-lY

    return tX,tY,bX,bY,etX,etY,ebX,ebY

def getRotation(bb): #read direction
    if max(bb[0][1],bb[1][1])<min(bb[2][1],bb[2][1]) and max(bb[0][0],bb[2][0])<min(bb[1][0],bb[2][0]):
        return 'left-right'
    elif max(bb[0][0],bb[1][0])<min(bb[2][0],bb[2][0]) and max(bb[1][1],bb[2][1])<min(bb[0][1],bb[2][1]):
        return 'up'
    elif min(bb[0][1],bb[1][1])>max(bb[2][1],bb[2][1]) and min(bb[0][0],bb[2][0])>max(bb[1][0],bb[2][0]):
        return 'right-left'
    elif max(bb[2][0],bb[2][0])<min(bb[0][0],bb[1][0]) and max(bb[2][1],bb[0][1])<min(bb[2][1],bb[1][1]):
        return 'down'
    else:
        return 'diag'

def getNumSteps(points):
    topDist=0
    botDist=0
    avgH=0
    for i in range(len(points)-1):
        topDist += math.sqrt((points[i][0][0]-points[i+1][0][0])**2 + (points[i][1][0]-points[i+1][1][0])**2)
        botDist += math.sqrt((points[i][0][1]-points[i+1][0][1])**2 + (points[i][1][1]-points[i+1][1][1])**2)
        avgH += math.sqrt((points[i][0][0]-points[i][0][1])**2 + (points[i][1][0]-points[i][1][1])**2)
    avgH += math.sqrt((points[-1][0][0]-points[-1][0][1])**2 + (points[-1][1][0]-points[-1][1][1])**2)
    avgH /= len(points)
    #if (math.ceil(max(topDist,botDist)/avgH) == 1):
    #    import pdb; pdb.set_trace();
    return math.ceil(max(topDist,botDist)/avgH)