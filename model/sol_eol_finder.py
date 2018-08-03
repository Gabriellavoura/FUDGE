import torch
from torch import nn
from . import vgg
from base import BaseModel

class SOL_EOL_Finder(BaseModel):
    def __init__(self, config): # predCount, base_0, base_1):
        super(SOL_EOL_Finder, self).__init__(config)
        self.predCount = config['number_of_object_types']
        if "norm_type" in config:
            batch_norm=config["norm_type"]=='batch_norm'
            weight_norm=config["norm_type"]=='weight_norm'
        else:
            batch_norm=False
            weight_norm=False
        self.cnn, self.scale = vgg.vgg11_custOut(self.predCount*5,batch_norm=batch_norm, weight_norm=weight_norm)
        #self.base_0 = config['base_0']
        #self.base_1 = config['base_1']

    def forward(self, img):
        y = self.cnn(img)

        #priors_0 = Variable(torch.arange(0,y.size(2)).type_as(img.data), requires_grad=False)[None,:,None]
        priors_0 = torch.arange(0,y.size(2)).type_as(img.data)[None,:,None]
        priors_0 = (priors_0 + 0.5) * self.scale #self.base_0
        priors_0 = priors_0.expand(y.size(0), priors_0.size(1), y.size(3))
        priors_0 = priors_0[:,None,:,:]

        #priors_1 = Variable(torch.arange(0,y.size(3)).type_as(img.data), requires_grad=False)[None,None,:]
        priors_1 = torch.arange(0,y.size(3)).type_as(img.data)[None,None,:]
        priors_1 = (priors_1 + 0.5) * self.scale #elf.base_1
        priors_1 = priors_1.expand(y.size(0), y.size(2), priors_1.size(2))
        priors_1 = priors_1[:,None,:,:]

        allPreds=[]
        for i in range(self.predCount):
            predictions = torch.cat([
                torch.sigmoid(y[:,0+i:1+i,:,:]),    #confidence
                y[:,1+i:2+i,:,:] + priors_1,        #x-center
                y[:,2+i:3+i,:,:] + priors_0,        #y-center
                y[:,3+i:4+i,:,:],                   #rotation (radians)
                y[:,4+i:5+i,:,:]                    #scale (half-height?)
            ], dim=1)

            predictions = predictions.transpose(1,3).contiguous()
            predictions = predictions.view(predictions.size(0),-1,5)
            allPreds.append(predictions)

        return allPreds
