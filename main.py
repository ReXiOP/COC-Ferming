from logger import logger
import cv2
import time
import os
import numpy as np
import config
from bot_core import BotCore
from vision import Vision
from banner import print_banner

class CocBot:
    def __init__(self):
        self.bot = BotCore()
        self.vision = Vision(templates_dir="templates")
        
        # State machine
        self.state = "HOME_SCREEN"
        self.running = True
        self.paused = False
        self.state_start_time = time.time()
        self.stuck_notified = False

        # White-screen watchdog
        self._white_screen_since = None   # timestamp when white screen first detected
        self._WHITE_SCREEN_TIMEOUT = 60   # seconds before restart

    def start(self):
        print_banner()
        logger.info("Starting Clash of Clans Farming Bot...")
        
        if not self.bot.connect():
            logger.info("Could not connect to Emulator. Ensure it's running and ADB is enabled.")
            return

        logger.info("Connected successfully!")

        # ── Auto-launch CoC if it is not already in the foreground ──────
        if not self.bot.is_app_running():
            logger.info("Clash of Clans is not running. Launching via ADB...")
            self.bot.launch_app()
            logger.info("Waiting 15 s for the game to load...")
            time.sleep(15)
        else:
            logger.info("Clash of Clans is already running.")
        # ────────────────────────────────────────────────────────────────
        
        import telegram_bot
        telegram_bot.send_telegram_message("✅ <b>CocBot Started</b>\nThe bot has been successfully launched and connected to the emulator.")
        telegram_bot.start_polling(self)
        
        # Make sure templates are re-loaded
        self.vision.templates.clear()
        self.vision.load_templates()
        
        self.run_loop()

    def run_loop(self):
        try:
            while self.running:
                if self.paused:
                    time.sleep(1)
                    continue

                screen = self.bot.take_screenshot("current_screen.png")
                if screen is None:
                    time.sleep(1)
                    continue

                # ── White-screen watchdog ────────────────────────────────
                if self._is_white_screen(screen):
                    if self._white_screen_since is None:
                        self._white_screen_since = time.time()
                        logger.warning("White screen detected – starting watchdog timer...")
                    elif time.time() - self._white_screen_since >= self._WHITE_SCREEN_TIMEOUT:
                        logger.error(
                            f"White screen persisted for >={self._WHITE_SCREEN_TIMEOUT}s. "
                            "Force-restarting Clash of Clans..."
                        )
                        try:
                            import telegram_bot
                            telegram_bot.send_telegram_message(
                                "⚠️ <b>White Screen Detected!</b>\n"
                                f"The game was stuck on a white screen for {self._WHITE_SCREEN_TIMEOUT}s.\n"
                                "Restarting Clash of Clans via ADB..."
                            )
                        except Exception:
                            pass
                        self.bot.force_restart_app()
                        logger.info("Waiting 20 s for the game to reload after restart...")
                        time.sleep(20)
                        self._white_screen_since = None
                        self.state = "HOME_SCREEN"
                        self.state_start_time = time.time()
                    else:
                        elapsed_ws = time.time() - self._white_screen_since
                        logger.debug(f"White screen watchdog: {elapsed_ws:.0f}s / {self._WHITE_SCREEN_TIMEOUT}s")
                    time.sleep(1)
                    continue
                else:
                    # Screen is no longer white – reset watchdog
                    if self._white_screen_since is not None:
                        logger.info("White screen cleared.")
                        self._white_screen_since = None
                # ──────────────────────────────────────────────────────────

                # 1. Determine current state based on what we see on screen
                state = self.detect_state(screen)
                if state != self.state:
                    logger.info(f"[STATE CHANGE] {self.state} -> {state}")
                    self.state = state
                    self.state_start_time = time.time()
                    self.stuck_notified = False
                else:
                    logger.debug(f"Detected State: {self.state}")
                    
                    elapsed = time.time() - self.state_start_time
                    # 2 minutes for all states
                    timeout = 120
                    
                    if elapsed > timeout and not self.stuck_notified:
                        error_msg = f"⚠️ <b>Bot Stuck!</b>\nThe bot has been stuck in the {self.state} state for {timeout//60} minutes. Please check the emulator."
                        logger.error(error_msg.replace("<b>", "").replace("</b>", "").replace("⚠️ ", ""))
                        
                        try:
                            import telegram_bot
                            telegram_bot.send_telegram_message(error_msg)
                        except Exception as e:
                            logger.error(f"Failed to send Telegram notification: {e}")
                            
                        self.stuck_notified = True

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

    # ------------------------------------------------------------------
    # White-screen helpers
    # ------------------------------------------------------------------

    def _is_white_screen(self, screen, threshold=0.85):
        """
        Return True if more than `threshold` fraction of the screen pixels
        are nearly white (R, G, B all >= 240).
        This catches the loading/blank-white freeze that CoC shows occasionally.
        """
        if screen is None:
            return False
        # screen is BGR; white means all channels >= 240
        white_mask = np.all(screen >= 240, axis=2)
        white_ratio = white_mask.sum() / white_mask.size
        return white_ratio >= threshold

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
        # Periodically check loot (every 30 mins = 1800s)
        current_time = time.time()
        if not hasattr(self, 'last_loot_check_time'):
            self.last_loot_check_time = 0
            
        if current_time - self.last_loot_check_time > 800:
            logger.info("Performing periodic loot check...")
            self.last_loot_check_time = current_time
            text, numbers = self.vision.read_loot(screen)
            if numbers:
                is_full = False
                for num in numbers:
                    # Check if over 18M (close to 18.5M max gold or 21M max elixir)
                    if num >= 18000000: 
                        is_full = True
                        break
                if is_full:
                    logger.info("Storage is full! Sending alert...")
                    import telegram_bot
                    telegram_bot.send_telegram_message("🚨 <b>Storage Full Alert!</b> 🚨\nYour storages are at max capacity.")
                    telegram_bot.send_telegram_loot(self)

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
        
        h, w = screen.shape[:2]
        
        # Define deployment zones
        edge_start = (int(w * 0.5), int(h * 0.1))
        edge_end = (int(w * 0.9), int(h * 0.5))
        core = (int(w * 0.5), int(h * 0.5))
        
        YOLO_CLASSES = [
            'ad', 'airsweeper', 'bombtower', 'canon', 'clancastle', 'eagle', 
            'inferno', 'kingpad', 'mortar', 'queenpad', 'rcpad', 'scattershot', 
            'wardenpad', 'wizztower', 'xbow'
        ]
        
        # ============================================================
        # PHASE 0: PRE-SCAN BASE WITH YOLO (before any troops deploy)
        # ============================================================
        logger.info("=" * 50)
        logger.info("[INTEL] Scanning enemy base with YOLOv5...")
        
        # Take a clean screenshot of the base before deployment bar obscures it
        scan_screen = self.bot.take_screenshot("base_scan.png")
        
        # Run YOLO detection on the full base
        defense_map = {}  # { "eagle": [(x,y,conf), ...], "inferno": [(x,y,conf), ...] }
        all_defenses = []
        
        if scan_screen is not None:
            detections = self.vision.detect_objects(scan_screen)
            for cls_name, cx, cy, conf in detections:
                if cls_name not in defense_map:
                    defense_map[cls_name] = []
                defense_map[cls_name].append((cx, cy, conf))
                all_defenses.append((cls_name, cx, cy, conf))
            
            # Log the intel report
            if defense_map:
                logger.info(f"[INTEL] Detected {len(all_defenses)} structures:")
                for cls, positions in defense_map.items():
                    coords = [f"({x},{y})" for x, y, c in positions]
                    logger.info(f"  - {cls}: {', '.join(coords)}")
            else:
                logger.info("[INTEL] No defenses detected by YOLO.")
        
        logger.info("=" * 50)
        
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

        def get_cached_target(target_class):
            """Get the best target position from cached YOLO scan."""
            if target_class in defense_map and defense_map[target_class]:
                best = max(defense_map[target_class], key=lambda d: d[2])
                return best[0], best[1]
            return None, None

        # Defense threat priority for smart freeze (highest threat first)
        DEFENSE_PRIORITY = [
            "eagle",        # Eagle Artillery - most dangerous
            "inferno",      # Inferno Tower - melts everything
            "scattershot",  # Scattershot - heavy splash
            "xbow",         # X-Bow - high DPS
            "ad",           # Air Defense - kills dragons
            "wizztower",    # Wizard Tower - splash air
            "airsweeper",   # Air Sweeper - pushes dragons back
        ]

        def get_smart_freeze_targets(count):
            """Return a list of (class, x, y) targets sorted by threat priority and confidence."""
            priority_targets = []
            for defense_class in DEFENSE_PRIORITY:
                if defense_class in defense_map:
                    # Sort defenses of this class by confidence (highest first)
                    sorted_defenses = sorted(defense_map[defense_class], key=lambda d: d[2], reverse=True)
                    for x, y, conf in sorted_defenses:
                        # Only target if confidence is decently high to avoid false positives
                        if conf >= 0.50:
                            priority_targets.append((defense_class, x, y, conf))
                            
            # Fallback: if we didn't find enough high-confidence targets, include lower confidence ones
            if len(priority_targets) < count:
                for defense_class in DEFENSE_PRIORITY:
                    if defense_class in defense_map:
                        sorted_defenses = sorted(defense_map[defense_class], key=lambda d: d[2], reverse=True)
                        for x, y, conf in sorted_defenses:
                            if conf < 0.50 and (defense_class, x, y, conf) not in priority_targets:
                                priority_targets.append((defense_class, x, y, conf))
                                
            # Already sorted by priority order, and now within each priority, by highest confidence
            return priority_targets[:count]

        HERO_NAMES = [
            "barbarian_king", "archer_queen", "grand_warden",
            "minion_prince", "royal_champion", "battle_machine"
        ]

        def deploy_card(troop_name, count, target_area, verify_depleted=True, use_ability=None):
            if count <= 0:
                return True
            
            # Auto-skip verification for single-use troops (heroes, siege machines)
            # They only have 1 unit so no need to re-check after deploying
            original_count = count
            if original_count == 1:
                verify_depleted = False
            
            # Default: activate ability for heroes automatically
            if use_ability is None:
                use_ability = troop_name in HERO_NAMES
                
            threshold = 0.55 if troop_name in ["grand_warden", "minion_prince", "stone_slammer", "barbarian_king", "archer_queen", "royal_champion", "battle_machine"] else 0.7
            
            while True:
                current_screen = self.bot.take_screenshot("temp_screen.png")
                if current_screen is None:
                    time.sleep(0.3)
                    continue
                    
                match = self.vision.find_image(troop_name, current_screen, threshold=threshold, check_saturation=True)
                if not match:
                    # One quick swipe to check for hidden troops
                    self.bot.swipe(int(w * 0.8), int(h * 0.92), int(w * 0.2), int(h * 0.92), duration=0.2)
                    time.sleep(0.3)
                    
                    current_screen = self.bot.take_screenshot("temp_screen.png")
                    if current_screen is not None:
                        match = self.vision.find_image(troop_name, current_screen, threshold=threshold, check_saturation=True)
                        
                    if not match:
                        logger.info(f"[DEPLOY] '{troop_name}' not on bar. Skipping.")
                        return True
                    
                card_x, card_y, _ = match
                logger.info(f"[DEPLOY] Deploying {troop_name}...")
                
                # Select the card
                self.bot.tap(card_x, card_y)
                time.sleep(0.1)
                
                # Drop rapidly based on target
                actual_taps = max(1, count)
                
                if target_area == "single":
                    mid_x = (edge_start[0] + edge_end[0]) // 2
                    mid_y = (edge_start[1] + edge_end[1]) // 2
                    for _ in range(actual_taps):
                        self.bot.tap(mid_x, mid_y)
                        time.sleep(0.03)
                        
                elif target_area == "edge":
                    points = generate_line_points(edge_start, edge_end, actual_taps)
                    for px, py in points:
                        self.bot.tap(px, py)
                        time.sleep(0.03)
                        
                elif target_area == "core":
                    for _ in range(actual_taps):
                        self.bot.tap(core[0], core[1])
                        time.sleep(0.03)
                        
                elif target_area == "dynamic_dragon":
                    # Use live scan for dragons (they move)
                    target_x, target_y = None, None
                    for d_temp in ["dynamic_dragon_1", "dynamic_dragon_2"]:
                        d_match = self.vision.find_image(d_temp, current_screen, threshold=0.5)
                        if d_match:
                            target_x, target_y, _ = d_match
                            break
                            
                    # Create a spread pattern so spells don't drop on the exact same pixel
                    # 1st spell: Center
                    # 2nd spell: Up-Left
                    # 3rd spell: Down-Right
                    offsets = [(0, 0), (-60, -40), (60, 40), (60, -40), (-60, 40)]
                    
                    if target_x is not None:
                        for i in range(actual_taps):
                            ox, oy = offsets[i % len(offsets)]
                            # Select card again before each drop to ensure it registers
                            self.bot.tap(card_x, card_y)
                            time.sleep(0.1)
                            self.bot.tap(target_x + ox, target_y + oy)
                            time.sleep(0.1)
                    else:
                        # Fallback: between edge and core
                        push_x = (edge_start[0] + edge_end[0] + core[0] * 2) // 4
                        push_y = (edge_start[1] + edge_end[1] + core[1] * 2) // 4
                        for i in range(actual_taps):
                            ox, oy = offsets[i % len(offsets)]
                            self.bot.tap(card_x, card_y)
                            time.sleep(0.1)
                            self.bot.tap(push_x + ox, push_y + oy)
                            time.sleep(0.1)
                            
                elif target_area == "dynamic_defense":
                    # Use CACHED defense positions from pre-scan!
                    if all_defenses:
                        logger.info(f"[INTEL] Using {len(all_defenses)} cached defense positions!")
                        for i in range(actual_taps):
                            det = all_defenses[i % len(all_defenses)]
                            cls_name, tx, ty, conf = det
                            logger.info(f"  -> Dropping on {cls_name} at ({tx},{ty})")
                            self.bot.tap(tx, ty)
                            time.sleep(0.03)
                    else:
                        logger.info("[INTEL] No cached defenses. Falling back to core.")
                        for _ in range(actual_taps):
                            self.bot.tap(core[0], core[1])
                            time.sleep(0.03)
                            
                elif target_area == "smart_freeze":
                    # Smart freeze: prioritize highest-threat defenses!
                    targets = get_smart_freeze_targets(actual_taps)
                    if targets:
                        logger.info(f"[SMART FREEZE] Targeting {len(targets)} high-priority defenses!")
                        for cls_name, tx, ty, conf in targets:
                            logger.info(f"  [FREEZE] {cls_name} at ({tx},{ty}) [conf:{conf:.2f}]")
                            # Select freeze spell card again for each tap
                            self.bot.tap(card_x, card_y)
                            time.sleep(0.1)
                            self.bot.tap(tx, ty)
                            time.sleep(0.3)
                    else:
                        logger.info("[SMART FREEZE] No defenses found. Dropping at core.")
                        for _ in range(actual_taps):
                            self.bot.tap(core[0], core[1])
                            time.sleep(0.03)
                            
                elif target_area == "townhall":
                    # Use cached TH position from pre-scan
                    tx, ty = get_cached_target("th13")
                    if tx is not None:
                        logger.info(f"[INTEL] Town Hall found at ({tx},{ty}) from pre-scan!")
                        for _ in range(actual_taps):
                            self.bot.tap(tx, ty)
                            time.sleep(0.03)
                    else:
                        logger.info("[INTEL] Town Hall not in pre-scan. Dropping at core.")
                        for _ in range(actual_taps):
                            self.bot.tap(core[0], core[1])
                            time.sleep(0.03)
                            
                elif target_area in YOLO_CLASSES:
                    # Use CACHED positions from pre-scan!
                    tx, ty = get_cached_target(target_area)
                    if tx is not None:
                        positions = defense_map.get(target_area, [])
                        logger.info(f"[INTEL] Using cached {target_area} positions ({len(positions)} found)!")
                        for i in range(actual_taps):
                            pos = positions[i % len(positions)]
                            logger.info(f"  -> Dropping on {target_area} at ({pos[0]},{pos[1]})")
                            self.bot.tap(pos[0], pos[1])
                            time.sleep(0.03)
                    else:
                        logger.info(f"[INTEL] '{target_area}' not in pre-scan. Falling back to core.")
                        for _ in range(actual_taps):
                            self.bot.tap(core[0], core[1])
                            time.sleep(0.03)
                        
                time.sleep(0.1)

                # ── Hero ability activation ──────────────────────────────
                if use_ability and troop_name in HERO_NAMES:
                    logger.info(f"[ABILITY] Waiting 1s then activating {troop_name} ability...")
                    time.sleep(3.0)
                    # Tap the card again to trigger the ability
                    self.bot.tap(card_x, card_y)
                    logger.info(f"[ABILITY] {troop_name} ability activated!")
                    time.sleep(0.2)
                # ────────────────────────────────────────────────────────
                
                if not verify_depleted:
                    return True
                    
                current_screen = self.bot.take_screenshot("temp_screen.png")
                if current_screen is None:
                    time.sleep(0.3)
                    return True
                    
                count = 1

        # ============================================================
        # EXECUTE DEPLOYMENT SEQUENCE
        # ============================================================
        logger.info("Executing Dynamic Deployment Sequence...")
        
        # Scroll village map to top
        self.bot.swipe(int(w * 0.5), int(h * 0.3), int(w * 0.5), int(h * 0.7), duration=0.3)
        time.sleep(0.5)
        
        # Scroll troop bar to the start
        logger.info("Scrolling troop bar to start...")
        self.bot.swipe(int(w * 0.2), int(h * 0.92), int(w * 0.8), int(h * 0.92), duration=0.3)
        time.sleep(0.5)
        
        for step in config.DEPLOYMENT_SEQUENCE:
            troop_name = step.get("name")
            count = step.get("count", 1)
            target_area = step.get("target", "edge")
            delay = step.get("delay", 0)
            verify = step.get("verify", True)
            use_ability = step.get("use_ability", None)  # None = auto-detect for heroes
            
            if count > 0:
                logger.info(f"--- Step: {troop_name} x{count} -> {target_area} ---")
                deploy_card(troop_name, count, target_area, verify_depleted=verify, use_ability=use_ability)
                
                if delay > 0:
                    logger.info(f"Waiting {delay}s...")
                    time.sleep(delay)
        
        logger.info("All troops deployed! Monitoring for Return Home...")

    def handle_battle_finished(self, screen):
        """Logic for returning home after a battle ends"""
        match = self.vision.find_image("return_home_button", screen, threshold=0.75)
        if match:
            x, y, _ = match
            logger.info(f"Found 'Return Home' button at ({x}, {y}). Clicking...")
            self.bot.tap(x, y)
            time.sleep(3)

if __name__ == "__main__":
    bot = CocBot()
    bot.start()
