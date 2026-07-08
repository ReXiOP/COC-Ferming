import shutil
import os

templates_dir = r"c:\Users\sawban\Desktop\coc-tools\templates"

# 1. grand_warden.png is actually stone_slammer
src_wrong_warden = os.path.join(templates_dir, "grand_warden.png")
dst_correct_slammer = os.path.join(templates_dir, "stone_slammer.png")

# 2. image copy 3.png is the real grand warden
src_real_warden = r"c:\Users\sawban\Desktop\coc-tools\image copy 3.png"
dst_real_warden = os.path.join(templates_dir, "grand_warden.png")

# Rename the wrong warden to stone slammer
try:
    if os.path.exists(src_wrong_warden):
        # We use shutil.move to overwrite stone_slammer.png
        shutil.move(src_wrong_warden, dst_correct_slammer)
        print("Fixed stone_slammer.png!")
except Exception as e:
    print(f"Error moving: {e}")

# Copy the real warden
try:
    if os.path.exists(src_real_warden):
        shutil.copy2(src_real_warden, dst_real_warden)
        print("Fixed grand_warden.png!")
except Exception as e:
    print(f"Error copying: {e}")
