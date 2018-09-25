import os
import json
import logging
import argparse
import torch
from model.model import *
from model.unet import UNet
from model.sol_eol_finder import SOL_EOL_Finder
from model.detector import Detector
from model.line_follower import LineFollower
from model.metric import *
from data_loader import getDataLoader
from utils.printers import *
import math
from collections import defaultdict

from datasets.forms_detect import FormsDetect
from datasets import forms_detect

logging.basicConfig(level=logging.INFO, format='')


def main(resume,saveDir,numberOfImages,index,gpu=None, shuffle=False):
    np.random.seed(1234)
    checkpoint = torch.load(resume)
    config = checkpoint['config']
    config['data_loader']['batch_size']=math.ceil(config['data_loader']['batch_size']/2)
    config['data_loader']['shuffle']=shuffle
    config['validation']['shuffle']=shuffle
    #config['validation']

    #print(config['data_loader'])
    data_loader, valid_data_loader = getDataLoader(config,'train')
    #ttt=FormsDetect(dirPath='/home/ubuntu/brian/data/forms',split='train',config={'crop_to_page':False,'rescale_range':[450,800],'crop_params':{"crop_size":512},'no_blanks':True, "only_types": ["text_start_gt"], 'cache_resized_images': True})
    #data_loader = torch.utils.data.DataLoader(ttt, batch_size=16, shuffle=False, num_workers=5, collate_fn=forms_detect.collate)
    #valid_data_loader = data_loader.split_validation()

    model = eval(config['arch'])(config['model'])
    model.eval()
    model.summary()

    if gpu is not None:
        model = model.to(gpu)

    metrics = [eval(metric) for metric in config['metrics']]

    model.load_state_dict(checkpoint['state_dict'])

    #if "class" in config["trainer"]:
    #    trainer_class = config["trainer"]["class"]
    #else:
    #    trainer_class = "Trainer"

    #saveFunc = eval(trainer_class+'_printer')
    saveFunc = eval(config['data_loader']['data_set_name']+'_printer')

    step=5
    batchSize = config['data_loader']['batch_size']

    #numberOfImages = numberOfImages//config['data_loader']['batch_size']
    print(len(data_loader))
    train_iter = iter(data_loader)
    valid_iter = iter(valid_data_loader)

    if index is None:
        trainDir = os.path.join(saveDir,'train_'+config['name'])
        validDir = os.path.join(saveDir,'valid_'+config['name'])
        if not os.path.isdir(trainDir):
            os.mkdir(trainDir)
        if not os.path.isdir(validDir):
            os.mkdir(validDir)

        val_metrics_sum = np.zeros(len(metrics))
        val_metrics_list = defaultdict(lambda: defaultdict(list))
        val_comb_metrics = defaultdict(list)

        curVI=0

        for index in range(0,numberOfImages,step*batchSize):
            for trainIndex in range(index,index+step*batchSize, batchSize):
                if trainIndex/batchSize < len(data_loader):
                    print('train batch index: {}/{}'.format(trainIndex/batchSize,len(data_loader)),end='\r')
                    #data, target = train_iter.next() #data_loader[trainIndex]
                    #dataT = _to_tensor(gpu,data)
                    #output = model(dataT)
                    #data = data.cpu().data.numpy()
                    #output = output.cpu().data.numpy()
                    #target = target.data.numpy()
                    #metricsO = _eval_metrics_ind(metrics,output, target)
                    saveFunc(config,train_iter.next(),model,gpu,metrics,trainDir,trainIndex)
            
            for validIndex in range(index,index+step*batchSize, batchSize):
                if validIndex/batchSize < len(valid_data_loader):
                    print('valid batch index: {}/{}'.format(validIndex/batchSize,len(valid_data_loader)),end='\r')
                    #data, target = valid_iter.next() #valid_data_loader[validIndex]
                    curVI+=0
                    #dataT  = _to_tensor(gpu,data)
                    #output = model(dataT)
                    #data = data.cpu().data.numpy()
                    #output = output.cpu().data.numpy()
                    #target = target.data.numpy()
                    #metricsO = _eval_metrics_ind(metrics,output, target)
                    metricsO = saveFunc(config,valid_iter.next(),model,gpu,metrics,validDir,validIndex)
                    if type(metricsO) == dict:
                        for typ,typeLists in metricsO.items():
                            for name,lst in typeLists.items():
                                val_metrics_list[typ][name]+=lst
                                val_comb_metrics[typ]+=lst
                    else:
                        val_metrics_sum += metricsO.sum(axis=0)/metricsO.shape[0]
                    
        if gpu is not None:
            try:
                for vi in range(curVI,len(valid_data_loader)):
                    print('valid batch index: {}\{} (not save)'.format(vi,len(valid_data_loader)),end='\r')
                    #data, target = valid_iter.next() #valid_data_loader[validIndex]
                    #data  = _to_tensor(gpu,data)
                    #output = model(data)
                    #output = output.cpu().data.numpy()
                    #target = target.data.numpy()
                    #metricsO = _eval_metrics(metrics,output, target)
                    metricsO = saveFunc(config,train_iter.next(),model,gpu,metrics)
                    if type(metricsO) == dict:
                        for typ,typeLists in metricsO.items():
                            for name,lst in typeLists.items():
                                val_metrics_list[typ][name]+=lst
                                val_comb_metrics[typ]+=lst
                    else:
                        val_metrics_sum += metricsO.sum(axis=0)/metricsO.shape[0]
            except StopIteration:
                print('ERROR: ran out of valid batches early. Expected {} more'.format(len(valid_data_loader)-vi))
            
            val_metrics_sum /= len(valid_data_loader)
            print('Validation metrics')
            for i in range(len(metrics)):
                print(metrics[i].__name__ + ': '+str(val_metrics_sum[i]))
            for typ in val_comb_metrics:
                print('{} overall mean: {}, std {}'.format(typ,np.mean(val_comb_metrics[typ]), np.std(val_comb_metrics[typ])))
                for name, typeLists in val_metrics_list[typ].items():
                    print('{} {} mean: {}, std {}'.format(typ,name,np.mean(typeLists),np.std(typeLists)))

    else:
        batchIndex = index//batchSize
        inBatchIndex = index%batchSize
        for i in range(batchIndex+1):
            instance= train_iter.next()
        #data, target = data[inBatchIndex:inBatchIndex+1], target[inBatchIndex:inBatchIndex+1]
        #dataT = _to_tensor(gpu,data)
        #output = model(dataT)
        #data = data.cpu().data.numpy()
        #output = output.cpu().data.numpy()
        #target = target.data.numpy()
        #print (output.shape)
        #print ((output.min(), output.amin()))
        #print (target.shape)
        #print ((target.amin(), target.amin()))
        #metricsO = _eval_metrics_ind(metrics,output, target)
        saveFunc(instance,model,gpu,metrics,saveDir,batchIndex*batchSize)


if __name__ == '__main__':
    logger = logging.getLogger()

    parser = argparse.ArgumentParser(description='PyTorch Evaluator/Displayer')
    parser.add_argument('-c', '--checkpoint', default=None, type=str,
                        help='path to latest checkpoint (default: None)')
    parser.add_argument('-d', '--savedir', default=None, type=str,
                        help='path to directory to save result images (default: None)')
    parser.add_argument('-i', '--index', default=None, type=int,
                        help='index on instance to process (default: None)')
    parser.add_argument('-n', '--number', default=100, type=int,
                        help='number of images to save out (from each train and valid) (default: 100)')
    parser.add_argument('-g', '--gpu', default=None, type=int,
                        help='gpu number (default: cpu only)')
    parser.add_argument('-s', '--shuffle', default=False, type=bool,
                        help='shuffle data')

    args = parser.parse_args()

    config = None
    if args.checkpoint is None or args.savedir is None:
        print('Must provide checkpoint (with -c) and save dir (with -d)')
        exit()

    main(args.checkpoint, args.savedir, args.number, args.index, gpu=args.gpu, shuffle=args.shuffle)
