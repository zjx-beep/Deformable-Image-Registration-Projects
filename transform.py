# -*- coding: utf-8 -*-
"""
Created on Wed Mar 18 11:35:19 2020

@author: 起明
"""

import numpy as np
from scipy import ndimage
 
import torch
import torch.nn.functional as F
#import torchvision.transforms as transforms
        
class ToTensor(object):
    """Convert ndarrays in sample to Tensors."""
    def __call__(self, patch):
        if patch.dtype!=np.float32:
            patch = patch.astype('float32')
        return torch.from_numpy(patch)
        
class OneNorm(object):
    """Normalize Tensor image into range(0, 1).
    """
    def __init__(self, bound=None):#[-1000, 500]
        self.bound = bound
        
    def __call__(self, patch):
        patch = patch.astype('float32')
        if self.bound is None:
            min, max = patch.min(), patch.max()
        else:
            min, max = self.bound
        patch = (patch-min) / (max-min)
        patch[patch > 1] = 1
        patch[patch < 0] = 0
        return patch
    
def ReSample(image, old_spacing, new_spacing):
    '''
    resample the image from original spatial resolution to the given new_spacing.
    default: 3-order spline interpolation.
    :params:
        image: shape(height, width, channel)
        old_spacing: the old spacing of the input image, shape(depth,height,width),
        new_spacing: the new spacing of the output image, shape(depth,height,width).
    '''
    resize_factor = old_spacing / new_spacing
    new_real_shape = image.shape * resize_factor
    new_shape = np.round(new_real_shape)
    real_resize_factor = new_shape / image.shape
    new_spacing = old_spacing / real_resize_factor
    image = ndimage.interpolation.zoom(image, real_resize_factor, order=4, mode='nearest')
 
    return image, new_spacing
 
class CenterCrop(object):
    """crop image in the center
    input: residual
        image, shape(D, H, W)
        dims,
    output:
        image, image volumes cropped from input image.
        delta, list, the difference between two origins.
    """
    def __init__(self, residual=[0,0,0]):
        self.residual = residual
        
    def __call__(self, image, dims):
        #pad, if image.dims is lower than dims
        dims, shape = np.array(dims), np.array(image.shape)
        p = np.flip(dims - shape, axis=0)
        p[p<0] = 0
 
        p_h0, p_h1 = p // 2, p - p//2
        #(padLeft, padRight, padTop, padBottom, padFront, padBack)
        p3d = np.stack((p_h0, p_h1), axis=1).reshape(-1)
        #5D Tensor 
        image = torch.Tensor(image).unsqueeze(0).unsqueeze(0)           
        padded = F.pad(image, tuple(p3d), 'replicate')
        padded = padded.squeeze().numpy()
        #crop
        d0, h0, w0 = dims
        dim_hf0 = (np.array(padded.shape) - dims) // 2 + self.residual
        d_hf, h_hf, w_hf = dim_hf0
        cropped = padded[d_hf:d0+d_hf, h_hf:h0+h_hf, w_hf:w0+w_hf]
        
#        dim_hf1 = np.array(padded.shape) - dims - dim_hf0
        delta = np.flip(p_h0, axis=0)- dim_hf0
        return cropped, delta
 
def DiffAdjust(diff, cut=[0.01, 0.99]):
    #param: numpy.ndarray diff
    eps = 1e-5
    copy = diff.copy()
    # cut
    sort0 = sorted(copy.flatten().tolist())
    min_idx = int(len(sort0) * cut[0])
    max_idx = int(len(sort0) * cut[1])
    max = sort0[max_idx]
    min = sort0[min_idx]
    
    copy[copy>=max] = max
    copy[copy<=min] = min
    copy -= min
    ad_diff = copy /(max - min + eps)
    return ad_diff