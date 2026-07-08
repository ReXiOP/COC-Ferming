from logger import logger
import cv2
import time
import os
import numpy as np
import config
from bot_core import BotCore
from vision import Vision

class CocBot:
    def __init__(self):
        self.bot = BotCore()
        self.vision = Vision(templates_dir="templates")
        
        # State machine
        self.state = "HOME_SCREEN"
        self.running = True

    def start(self):
        logger.info("Starting Clash of Clans Farming Bot...")
        
        if not self.bot.connect():
            logger.info("Could not connect to Emulator. Ensure it's running and ADB is enabled.")
            return

        logger.info("Connected successfully!")
        
        # Make sure templates are re-loaded
        self.vision.templates.clear()
        self.vision.load_templates()
        
        self.run_loop()

    def run_loop(self):
        try:
            while self.running:
                screen = self.bot.take_screenshot("current_screen.png")
                if screen is None:
                    time.sleep(1)
                    continue

                # 1. Determine current state based on what we see on screen
                state = self.detect_state(screen)
                if state != self.state:
                    logger.info(f"[STATE CHANGE] {self.state} -> {state}")
                    self.state = state
                else:
                    logger.debug(f"Detected State: {self.state}")

                # 2. Execute action for that state
                if self.state == "HOME_SCREEN":
                    self.handle_home_screen(screen)
                elif self.state == "ARMY_OVERVIEW":
                    self.handle_army_overview(screen)
                elif self.state == "ATTACK_MENU":
                    self.handle_attack_menu(screen)
                elif self.state == "ENEMY_BASE":
                    self.handle_attacking(screen)
                elif self.state == "BATTLE_FINISHED":
                    self.handle_battle_finished(screen)
                else:
                    logger.debug("Unknown state. Waiting for troops to finish or screen to change...")
                    time.sleep(2)

        except KeyboardInterrupt:
            logger.info("\nBot stopped by user.")

    def detect_state(self, screen):
        """Determine what screen we are on based on visible buttons"""
        if self.vision.find_image("return_home_button", screen, threshold=0.65):
            return "BATTLE_FINISHED"
        if self.vision.find_image("next_button", screen, threshold=0.65):
            return "ENEMY_BASE"
        if self.vision.find_image("find_match_button", screen, threshold=0.75):
            return "ATTACK_MENU"
        if self.vision.find_image("attack_green_button", screen, threshold=0.7):
            return "ARMY_OVERVIEW"
        if self.vision.find_image("home_attack_button", screen, threshold=0.65):
            return "HOME_SCREEN"
        return "UNKNOWN"

    def handle_home_screen(self, screen):
        match = self.vision.find_image("home_attack_button", screen, threshold=0.65)
        if match:
            x, y, _ = match
            logger.info(f"Clicking Home 'Attack' button at ({x}, {y})...")
            self.bot.tap(x, y)
            time.sleep(2)
            
    def handle_army_overview(self, screen):
        match = self.vision.find_image("attack_green_button", screen, threshold=0.7)
        if match:
            x, y, _ = match
            logger.info(f"Clicking Army 'Attack' button at ({x}, {y})...")
            self.bot.tap(x, y)
            time.sleep(2)

    def handle_attack_menu(self, screen):
        match = self.vision.find_image("find_match_button", screen, threshold=0.75)
        if match:
            x, y, _ = match
            template_h = self.vision.templates["find_match_button"].shape[0]
            adjusted_y = y + int(template_h * 0.3) 
            logger.info(f"Clicking 'Find a Match' at ({x}, {adjusted_y})...")
            self.bot.tap(x, adjusted_y)
            logger.info("Searching for base...")
            time.sleep(5) 
            
    def handle_attacking(self, screen):
        logger.info("Commencing refined 'Smart' attack strategy!")
        
        # Take initial screenshot to detect Town Hall level
        initial_screen = self.bot.take_screenshot("temp_screen.png")
        if initial_screen is not None:
            th_level = "Unknown"
            # Detect TH
            for i in range(14, 0, -1):
                th_temp = f"th_{i}"
                if self.vision.find_image(th_temp, initial_screen, threshold=0.55):
                    th_level = str(i)
                    break
                for sub in [".1", ".2", ".3", ".4", ".5"]:
                    sub_temp = f"th_{i}{sub}"
                    if sub_temp in self.vision.templates:
                        if self.vision.find_image(sub_temp, initial_screen, threshold=0.55):
                            th_level = f"{i}{sub}"
                            break
                if th_level != "Unknown":
                    break
            
            logger.info(f"[BASE INFO] Enemy Town Hall Level: {th_level}")
        
        h, w = screen.shape[:2]
        
        # Define deployment zones
        # Top-Right edge: slightly inside the screen to avoid notification bars and red zones
        edge_start = (int(w * 0.5), int(h * 0.1))  # Top middle (10% from top)
        edge_end = (int(w * 0.9), int(h * 0.5))    # Right middle (10% from right edge)
        core = (int(w * 0.5), int(h * 0.5))
        
        YOLO_CLASSES = [
            'ad', 'airsweeper', 'bombtower', 'canon', 'clancastle', 'eagle', 
            'inferno', 'kingpad', 'mortar', 'queenpad', 'rcpad', 'scattershot', 
            'th13', 'wardenpad', 'wizztower', 'xbow'
        ]
        
        def generate_line_points(start, end, num_points):
            points = []
            if num_points <= 1:
                return [ ( (start[0]+end[0])//2, (start[1]+end[1])//2 ) ]
            for i in range(num_points):
                t = i / (num_points - 1)
                x = int(start[0] + t * (end[0] - start[0]))
                y = int(start[1] + t * (end[1] - start[1]))
                points.append((x, y))
            return points

        def deploy_card(troop_name, count, target_area, verify_depleted=True):
            if count <= 0:
                return True
                
            # Heroes and Siege Machines need a lower threshold because their health bar changes their appearance.
            # Regular troops and spells need a balanced threshold (0.7) so they don't accidentally match each other,
            # but they still match even if the remaining troop count number changes on the card!
            threshold = 0.55 if troop_name in ["grand_warden", "minion_prince", "stone_slammer", "barbarian_king", "archer_queen", "royal_champion", "battle_machine"] else 0.7
            
            while True:
                # Always take a fresh screenshot so we know the EXACT current position of the card,
                # because the troop bar shifts left whenever a troop is completely depleted!
                current_screen = self.bot.take_screenshot("temp_screen.png")
                if current_screen is None:
                    time.sleep(1)
                    continue
                    
                match = self.vision.find_image(troop_name, current_screen, threshold=threshold, check_saturation=True)
                if not match:
                    # Swipe right-to-left to reveal hidden troops on the right side of the bar
                    logger.debug(f"'{troop_name}' not immediately found. Swiping troop bar to check...")
                    self.bot.swipe(int(w * 0.8), int(h * 0.92), int(w * 0.2), int(h * 0.92), duration=0.5)
                    time.sleep(1.0)
                    
                    current_screen = self.bot.take_screenshot("temp_screen.png")
                    if current_screen is not None:
                        match = self.vision.find_image(troop_name, current_screen, threshold=threshold, check_saturation=True)
                        
                    if not match:
                        logger.info(f"[DEPLOY] Successfully deployed all '{troop_name}'.")
                        return True
                    
                card_x, card_y, _ = match
                logger.info(f"[DEPLOY] Active: Deploying {troop_name}...")
                
                # Select the card
                self.bot.tap(card_x, card_y)
                time.sleep(0.2)
                
                # Drop it rapidly based on count
                actual_taps = max(1, count)
                if target_area == "single":
                    mid_x = (edge_start[0] + edge_end[0]) // 2
                    mid_y = (edge_start[1] + edge_end[1]) // 2
                    for _ in range(actual_taps):
                        self.bot.tap(mid_x, mid_y)
                        time.sleep(0.05)
                elif target_area == "edge":
                    points = generate_line_points(edge_start, edge_end, actual_taps)
                    for px, py in points:
                        self.bot.tap(px, py)
                        time.sleep(0.05)
                elif target_area == "core":
                    for _ in range(actual_taps):
                        self.bot.tap(core[0], core[1])
                        time.sleep(0.05)
                elif target_area == "dynamic_dragon":
                    target_x, target_y = None, None
                    for d_temp in ["dynamic_dragon_1", "dynamic_dragon_2"]:
                        d_match = self.vision.find_image(d_temp, current_screen, threshold=0.5)
                        if d_match:
                            target_x, target_y, _ = d_match
                            logger.info(f"Found live dragon at {target_x}, {target_y}!")
                            break
                    if target_x is not None:
                        for _ in range(actual_taps):
                            self.bot.tap(target_x, target_y)
                            time.sleep(0.05)
                    else:
                        logger.info("Live dragon not found! Falling back to push zone.")
                        edge_mid_x = (edge_start[0] + edge_end[0]) // 2
                        edge_mid_y = (edge_start[1] + edge_end[1]) // 2
                        push_x = (edge_mid_x + core[0]) // 2
                        push_y = (edge_mid_y + core[1]) // 2
                        for _ in range(actual_taps):
                            self.bot.tap(push_x, push_y)
                            time.sleep(0.05)
                elif target_area == "dynamic_defense":
                    target_x, target_y = None, None
                    
                    # Try YOLO first
                    detections = self.vision.detect_objects(current_screen, target_classes=["inferno", "ad", "eagle", "scattershot", "xbow", "wizztower", "canon", "mortar", "bombtower"])
                    if detections:
                        logger.info(f"Found {len(detections)} live defenses via YOLO!")
                        for i in range(actual_taps):
                            det = detections[i % len(detections)]
                            cls_name, tx, ty, conf = det
                            logger.info(f"Dropping on {cls_name} at {tx}, {ty} (conf: {conf:.2f})")
                            self.bot.tap(tx, ty)
                            time.sleep(0.05)
                    else:
                        # Fallback to templates
                        for d_temp in ["dynamic_inferno", "dynamic_air_defense"]:
                            d_match = self.vision.find_image(d_temp, current_screen, threshold=0.55)
                            if d_match:
                                target_x, target_y, _ = d_match
                                logger.info(f"Found live defense ({d_temp}) at {target_x}, {target_y}!")
                                break
                        
                        if target_x is not None:
                            for _ in range(actual_taps):
                                self.bot.tap(target_x, target_y)
                                time.sleep(0.05)
                        else:
                            logger.info("Live defense not found! Falling back to core zone.")
                            for _ in range(actual_taps):
                                self.bot.tap(core[0], core[1])
                                time.sleep(0.05)
                elif target_area == "townhall":
                    target_x, target_y = None, None
                    
                    # Try YOLO first
                    detections = self.vision.detect_objects(current_screen, target_classes=["th13"])
                    if detections:
                        cls_name, target_x, target_y, conf = detections[0]
                        logger.info(f"Found enemy Town Hall via YOLO at {target_x}, {target_y}! (conf: {conf:.2f})")
                    else:
                        # Fallback to templates
                        for i in range(14, 0, -1):
                            th_temp = f"th_{i}"
                            d_match = self.vision.find_image(th_temp, current_screen, threshold=0.55)
                            if d_match:
                                target_x, target_y, _ = d_match
                                logger.info(f"Found enemy Town Hall (Level {i}) at {target_x}, {target_y}!")
                                break
                            for sub in [".1", ".2", ".3", ".4", ".5"]:
                                sub_temp = f"th_{i}{sub}"
                                if sub_temp in self.vision.templates:
                                    d_match = self.vision.find_image(sub_temp, current_screen, threshold=0.55)
                                    if d_match:
                                        target_x, target_y, _ = d_match
                                    logger.info(f"Found enemy Town Hall ({sub_temp}) at {target_x}, {target_y}!")
                                    break
                        if target_x is not None:
                            break
                            
                    if target_x is not None:
                        for _ in range(actual_taps):
                            self.bot.tap(target_x, target_y)
                            time.sleep(0.05)
                    else:
                        logger.info("Enemy Town Hall not found! Falling back to core zone.")
                        for _ in range(actual_taps):
                            self.bot.tap(core[0], core[1])
                            time.sleep(0.05)
                elif target_area in YOLO_CLASSES:
                    detections = self.vision.detect_objects(current_screen, target_classes=[target_area])
                    if detections:
                        logger.info(f"Found {len(detections)} instances of '{target_area}' via YOLO!")
                        for i in range(actual_taps):
                            det = detections[i % len(detections)]
                            cls_name, tx, ty, conf = det
                            logger.info(f"Dropping on {cls_name} at {tx}, {ty} (conf: {conf:.2f})")
                            self.bot.tap(tx, ty)
                            time.sleep(0.05)
                    else:
                        logger.info(f"Target '{target_area}' not found! Falling back to core zone.")
                        for _ in range(actual_taps):
                            self.bot.tap(core[0], core[1])
                            time.sleep(0.05)
                        
                time.sleep(0.5)
                
                if not verify_depleted:
                    return True
                    
                # Take a fresh screenshot to verify it actually disappeared
                current_screen = self.bot.take_screenshot("temp_screen.png")
                if current_screen is None:
                    time.sleep(1)
                    return True
                    
                # If we loop again, we only drop 1 at a time to catch any stragglers
                count = 1

        # EXECUTE DEPLOYMENT SEQUENCE
        logger.info("Executing Dynamic Deployment Sequence...")
        
        # Scroll the village map to the top
        logger.info("Scrolling the village map to the top...")
        # Swipe from top to bottom in the center to drag the map down (revealing the top)
        self.bot.swipe(int(w * 0.5), int(h * 0.3), int(w * 0.5), int(h * 0.8), duration=0.5)
        time.sleep(1.0)
        
        # Ensure troop bar is scrolled to the top (leftmost) position before deploying
        logger.info("Scrolling troop deployment bar to the top...")
        # Swipe left-to-right across the bottom 10% of the screen
        self.bot.swipe(int(w * 0.2), int(h * 0.92), int(w * 0.8), int(h * 0.92), duration=0.5)
        time.sleep(1.0) # Wait for swipe momentum to settle
        
        for step in config.DEPLOYMENT_SEQUENCE:
            troop_name = step.get("name")
            count = step.get("count", 1)
            target_area = step.get("target", "edge")
            delay = step.get("delay", 0)
            verify = step.get("verify", True) # Default to True so it loops until depleted
            
            if count > 0:
                logger.info(f"--- Sequence Step: {troop_name} x{count} -> {target_area} ---")
                deploy_card(troop_name, count, target_area, verify_depleted=verify)
                
                if delay > 0:
                    logger.info(f"Sequence delay: Waiting {delay} seconds...")
                    time.sleep(delay)
        
        logger.info("All troops and spells deployed! Bot will now monitor for the Return Home button...")
        # No need to sleep for 150 seconds anymore! 
        # The state machine will naturally wait in "UNKNOWN" until "BATTLE_FINISHED" appears.

    def handle_battle_finished(self, screen):
        """Logic for returning home after a battle ends"""
        match = self.vision.find_image("return_home_button", screen, threshold=0.75)
        if match:
            x, y, _ = match
            logger.info(f"Found 'Return Home' button at ({x}, {y}). Clicking...")
            self.bot.tap(x, y)
            time.sleep(3) # Wait for the loading screen back to home 

if __name__ == "__main__":
    bot = CocBot()
    bot.start()
