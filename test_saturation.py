import cv2
import numpy as np
import sys

def get_saturation(img_path):
    img = cv2.imread(img_path)
    if img is None:
        return -1
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    saturation = hsv[:, :, 1].mean()
    return saturation

gray_card = r"c:\Users\sawban\Desktop\coc-tools\image copy 2.png"
active_dragon = r"c:\Users\sawban\Desktop\coc-tools\templates\dragon.png"
active_spell = r"c:\Users\sawban\Desktop\coc-tools\templates\rage_spell.png"

print("Gray card saturation:", get_saturation(gray_card))
print("Active Dragon saturation:", get_saturation(active_dragon))
print("Active Rage Spell saturation:", get_saturation(active_spell))
