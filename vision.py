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

    def find_image(self, target_name, screen_img, threshold=0.8, check_saturation=False, full_screen_h=None):
        """
        Finds a template image within the screen image across multiple scales
        to automatically support any screen resolution.
        """
        if target_name not in self.templates:
            logger.info(f"Template '{target_name}' not found.")
            return None

        if screen_img is None:
            return None

        original_template = self.templates[target_name]
        sh, sw = screen_img.shape[:2]
        
        # The true screen height used for scaling
        true_h = full_screen_h if full_screen_h is not None else sh
        
        # We will track the best match across different scales
        best_match = None
        best_val = -1
        best_loc = None
        best_scale = 1.0
        best_template_shape = (0, 0)
        
        # Determine if we have a cached scale factor for this screen height
        if not hasattr(self, "cached_scale") or self.last_screen_h != true_h:
            self.cached_scale = None
            self.last_screen_h = true_h
            
        # Exactly calculate the scale based on the vertical resolution.
        # The templates were captured on a 900p screen (e.g. 1600x900).
        # Clash of Clans UI scales strictly with the screen height.
        if hasattr(self, "cached_scale") and self.cached_scale is not None:
            scales_to_check = [self.cached_scale]
        else:
            # Dynamically calculate exact scale
            exact_scale = true_h / 900.0
            # Test the exact scale, and slightly smaller/larger just in case of rounding
            scales_to_check = [exact_scale, exact_scale * 0.98, exact_scale * 1.02]

        for scale in scales_to_check:
            # Resize template
            th, tw = original_template.shape[:2]
            new_w, new_h = int(tw * scale), int(th * scale)
            
            # Skip if template becomes too small or larger than screen
            if new_w < 10 or new_h < 10 or new_h > sh or new_w > sw:
                continue
                
            template = cv2.resize(original_template, (new_w, new_h))
            
            # Perform template matching
            result = cv2.matchTemplate(screen_img, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            if max_val > best_val:
                best_val = max_val
                best_loc = max_loc
                best_scale = scale
                best_template_shape = (new_h, new_w)
                
        # If the best match meets our threshold
        if best_val >= threshold and best_loc is not None:
            # Cache the successful scale factor to speed up future searches on this screen size
            if self.cached_scale is None:
                logger.info(f"Screen scale factor automatically determined as {best_scale:.2f}x")
                self.cached_scale = best_scale
                
            h, w = best_template_shape
            
            if check_saturation:
                top_y, top_x = best_loc[1], best_loc[0]
                bottom_y, bottom_x = top_y + h, top_x + w
                
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
                        
            center_x = best_loc[0] + w // 2
            center_y = best_loc[1] + h // 2
            return (center_x, center_y, best_val)
        
        return None

    def find_all_images(self, target_name, screen_img, threshold=0.8):
        """
        Finds all occurrences of a template image within the screen image.
        Uses the cached scale factor if available.
        """
        if target_name not in self.templates:
            logger.info(f"Template '{target_name}' not found.")
            return []

        if screen_img is None:
            return []

        original_template = self.templates[target_name]
        sh, sw = screen_img.shape[:2]
        
        # Use cached scale if available, otherwise 1.0
        scale = getattr(self, "cached_scale", 1.0)
        if scale is None:
            scale = 1.0
            
        th, tw = original_template.shape[:2]
        new_w, new_h = int(tw * scale), int(th * scale)
        
        if new_w < 10 or new_h < 10 or new_h > sh or new_w > sw:
            return []
            
        template = cv2.resize(original_template, (new_w, new_h))
        result = cv2.matchTemplate(screen_img, template, cv2.TM_CCOEFF_NORMED)
        
        locations = np.where(result >= threshold)
        matches = []
        
        for pt in zip(*locations[::-1]):
            center_x = pt[0] + new_w // 2
            center_y = pt[1] + new_h // 2
            matches.append((center_x, center_y))
            
        filtered_matches = []
        for m in matches:
            is_new = True
            for fm in filtered_matches:
                if abs(m[0] - fm[0]) < new_w//2 and abs(m[1] - fm[1]) < new_h//2:
                    is_new = False
                    break
            if is_new:
                filtered_matches.append(m)
                
        return filtered_matches
        
    def read_loot(self, screen_img):
        if screen_img is None:
            return None, None
            
        # Initialize easyocr lazily
        if not hasattr(self, 'ocr_reader'):
            try:
                import easyocr
                self.ocr_reader = easyocr.Reader(['en'], gpu=torch.cuda.is_available())
            except Exception as e:
                logger.error(f"Failed to load easyocr: {e}")
                return None, None
                
        # Crop the top right area (approx 1350:1600, 20:150 for 1600x900)
        h, w = screen_img.shape[:2]
        crop = screen_img[int(h*0.02):int(h*0.2), int(w*0.8):w]
        
        # Save for telegram to send
        cv2.imwrite("loot_crop.png", crop)
        
        # Read text
        results = self.ocr_reader.readtext(crop)
        
        # Parse text (look for large numbers)
        import re
        numbers = []
        full_text = []
        for (bbox, text, prob) in results:
            full_text.append(text)
            clean = re.sub(r'[^0-9]', '', text)
            if clean:
                try:
                    numbers.append(int(clean))
                except:
                    pass
                
        # Return raw text and list of numbers found
        return " | ".join(full_text), numbers

if __name__ == "__main__":
    v = Vision()
    logger.info(f"Loaded {len(v.templates)} templates.")
