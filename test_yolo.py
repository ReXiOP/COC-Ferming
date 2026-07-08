import torch
original_load = torch.load
def safe_load(*args, **kwargs):
    kwargs['weights_only'] = False
    return original_load(*args, **kwargs)
torch.load = safe_load

import yolov5
model = yolov5.load('keremberke/yolov5s-clash-of-clans')
print("Model classes:", model.names)
