from logger import logger
import cv2
import numpy as np
import os
import torch
import warnings
import cv2
import numpy as np
import os

# Suppress PyTorch/YOLO deprecation warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="yolov5")
warnings.filterwarnings("ignore", category=FutureWarning, module="torch")

class Vision:
    def __init__(self, templates_dir="templates"):
        self.templates_dir = templates_dir
        self.templates = {}
        self.load_templates()
        self.yolo_model = None
        self._load_yolo()

    def _load_yolo(self):
        try:
            import yolov5
            
            # Patch torch.load to avoid PyTorch 2.6 weights_only restriction
            original_load = torch.load
            def safe_load(*args, **kwargs):
                kwargs['weights_only'] = False
                return original_load(*args, **kwargs)
            torch.load = safe_load

            self.yolo_model = yolov5.load('keremberke/yolov5s-clash-of-clans')
            self.yolo_model.conf = 0.15
            self.yolo_model.iou = 0.45
            self.yolo_model.agnostic = False
            self.yolo_model.multi_label = False
            self.yolo_model.max_det = 1000
            
            torch.load = original_load
            logger.info("YOLOv5 model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load YOLOv5 model: {e}")

    def detect_objects(self, screen_img, target_classes=None):
        """
        Runs YOLOv5 on the screen and returns a list of matching objects.
        Returns: list of (class_name, center_x, center_y, confidence)
        """
        if self.yolo_model is None or screen_img is None:
            return []
            
        rgb_img = cv2.cvtColor(screen_img, cv2.COLOR_BGR2RGB)
        results = self.yolo_model(rgb_img, size=640)
        
        predictions = results.pred[0]
        detections = []
        
        for pred in predictions:
            x1, y1, x2, y2, conf, cls_id = pred.tolist()
            cls_name = self.yolo_model.names[int(cls_id)]
            
            if target_classes and cls_name not in target_classes:
                continue
                
            center_x = int((x1 + x2) / 2)
            center_y = int((y1 + y2) / 2)
            detections.append((cls_name, center_x, center_y, float(conf)))
            
        return detections

    def load_templates(self):
        """Load all images from the templates directory"""
        if not os.path.exists(self.templates_dir):
            os.makedirs(self.templates_dir)
            logger.info(f"Created '{self.templates_dir}' directory. Please add template images here.")
            return

        for filename in os.listdir(self.templates_dir):
            if filename.endswith(".png") or filename.endswith(".jpg"):
                path = os.path.join(self.templates_dir, filename)
                template_img = cv2.imread(path)
                if template_img is not None:
                    name = os.path.splitext(filename)[0]
                    self.templates[name] = template_img
                    logger.debug(f"Loaded template: {name}")

    def find_image(self, target_name, screen_img, threshold=0.8, check_saturation=False):
        """
        Finds a template image within the screen image.
        Returns the (x, y) coordinates of the center of the match, or None if not found.
        """
        if target_name not in self.templates:
            logger.info(f"Template '{target_name}' not found.")
            return None

        if screen_img is None:
            return None

        template = self.templates[target_name]
        
        # Ensure template is not larger than screen to prevent OpenCV crashes
        th, tw = template.shape[:2]
        sh, sw = screen_img.shape[:2]
        if th > sh or tw > sw:
            scale = min(sh / th, sw / tw)
            new_w, new_h = int(tw * scale), int(th * scale)
            template = cv2.resize(template, (new_w, new_h))
            logger.debug(f"Resized template '{target_name}' from {tw}x{th} to {new_w}x{new_h} to fit screen.")
            th, tw = new_h, new_w # update dimensions for center calculation

        # Perform template matching
        # cv2.matchTemplate compares the template against overlapping regions of the screen image
        result = cv2.matchTemplate(screen_img, template, cv2.TM_CCOEFF_NORMED)
        
        # Get the best match position
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        if max_val >= threshold:
            # max_loc gives the top-left corner of the match
            # We want to return the center coordinates for clicking
            h, w = template.shape[:2]
            
            if check_saturation:
                top_y, top_x = max_loc[1], max_loc[0]
                bottom_y, bottom_x = top_y + h, top_x + w
                
                # Make sure bounds are valid
                top_y = max(0, top_y)
                bottom_y = min(sh, bottom_y)
                top_x = max(0, top_x)
                bottom_x = min(sw, bottom_x)
                
                matched_roi = screen_img[top_y:bottom_y, top_x:bottom_x]
                if matched_roi.size > 0:
                    hsv = cv2.cvtColor(matched_roi, cv2.COLOR_BGR2HSV)
                    saturation = hsv[:, :, 1].mean()
                    if saturation < 50:
                        logger.debug(f"Template '{target_name}' matched but is grayed out (sat: {saturation:.1f}).")
                        return None
                        
            center_x = max_loc[0] + w // 2
            center_y = max_loc[1] + h // 2
            return (center_x, center_y, max_val)
        
        return None

    def find_all_images(self, target_name, screen_img, threshold=0.8):
        """
        Finds all occurrences of a template image within the screen image.
        Returns a list of (x, y) coordinates of the centers of the matches.
        """
        if target_name not in self.templates:
            logger.info(f"Template '{target_name}' not found.")
            return []

        if screen_img is None:
            return []

        template = self.templates[target_name]
        
        th, tw = template.shape[:2]
        sh, sw = screen_img.shape[:2]
        if th > sh or tw > sw:
            scale = min(sh / th, sw / tw)
            new_w, new_h = int(tw * scale), int(th * scale)
            template = cv2.resize(template, (new_w, new_h))
            th, tw = new_h, new_w

        result = cv2.matchTemplate(screen_img, template, cv2.TM_CCOEFF_NORMED)
        
        # Find all locations where the match value is above the threshold
        locations = np.where(result >= threshold)
        
        matches = []
        
        # locations is a tuple of (y_coords, x_coords)
        for pt in zip(*locations[::-1]):  # zip to (x, y) pairs
            center_x = pt[0] + tw // 2
            center_y = pt[1] + th // 2
            matches.append((center_x, center_y))
            
        # Optional: Group close matches together to avoid clicking the same object multiple times
        # This is a simplified grouping approach
        filtered_matches = []
        for m in matches:
            is_new = True
            for fm in filtered_matches:
                # If distance is small, consider it the same object
                if abs(m[0] - fm[0]) < tw//2 and abs(m[1] - fm[1]) < th//2:
                    is_new = False
                    break
            if is_new:
                filtered_matches.append(m)
                
        return filtered_matches

if __name__ == "__main__":
    v = Vision()
    logger.info(f"Loaded {len(v.templates)} templates.")
