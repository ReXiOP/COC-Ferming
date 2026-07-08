from logger import logger
import adbutils
import time
import os
import cv2
import numpy as np

class BotCore:
    def __init__(self, serial=None):
        self.adb = adbutils.adb
        self.device = None
        self.serial = serial
        
    def connect(self, host="127.0.0.1", port=5554):
        """Connect to emulator (LDPlayer default is usually already attached as emulator-5554)"""
        logger.info("Checking for connected devices...")
        
        # First, check if any device is already attached (like emulator-5554)
        devices = self.adb.device_list()
        if devices:
            for d in devices:
                if self.serial is None or d.serial == self.serial:
                    self.device = d
                    logger.info(f"Connected to existing device: {self.device.serial}")
                    return True

        # If not, try to explicitly connect
        address = f"{host}:{port}"
        logger.info(f"Attempting manual connection to {address}...")
        try:
            self.adb.connect(address)
            for d in self.adb.device_list():
                if self.serial is None or d.serial == self.serial or d.serial == address:
                    self.device = d
                    logger.info(f"Connected to {self.device.serial}")
                    return True
            logger.info("Could not find the device after connecting.")
            return False
        except Exception as e:
            logger.info(f"Failed to connect: {e}")
            return False

    def take_screenshot(self, filename="screen.png"):
        """Takes a screenshot and returns it as a cv2 image array, also saves it if filename is provided"""
        if not self.device:
            logger.info("Not connected to a device.")
            return None
            
        try:
            # Capture screen using adbutils
            pil_img = self.device.screenshot()
            
            # Convert PIL image to cv2 image (numpy array)
            # PIL is RGB, OpenCV is BGR
            cv_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            
            if filename:
                cv2.imwrite(filename, cv_img)
                
            return cv_img
        except Exception as e:
            logger.info(f"Screenshot failed: {e}")
            return None

    def tap(self, x, y):
        """Tap at the given coordinates"""
        if not self.device:
            return False
        try:
            self.device.click(x, y)
            logger.debug(f"Tapped at ({x}, {y})")
            return True
        except Exception as e:
            logger.info(f"Tap failed: {e}")
            return False
            
    def swipe(self, x1, y1, x2, y2, duration=0.5):
        """Swipe from (x1, y1) to (x2, y2)"""
        if not self.device:
            return False
        try:
            self.device.swipe(x1, y1, x2, y2, duration)
            logger.info(f"Swiped from ({x1}, {y1}) to ({x2}, {y2})")
            return True
        except Exception as e:
            logger.info(f"Swipe failed: {e}")
            return False

if __name__ == "__main__":
    bot = BotCore()
    if bot.connect():
        bot.take_screenshot("test_screenshot.png")
