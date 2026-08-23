import os
import time
import threading
import requests
from logger import logger
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/"

def send_telegram_message(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = API_URL + "sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": {
            "keyboard": [[{"text": "/status"}, {"text": "/loot"}], [{"text": "/pause"}, {"text": "/resume"}], [{"text": "/restart"}, {"text": "/device"}]],
            "resize_keyboard": True
        }
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        logger.error(f"Failed to send telegram message: {e}")

def send_telegram_status(bot_instance):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    
    # 1. Read last 10 logs
    log_text = "No logs available."
    try:
        if os.path.exists('logs/bot.log'):
            with open('logs/bot.log', 'r') as f:
                lines = f.readlines()
                last_10 = lines[-10:]
                log_text = "".join(last_10)
    except Exception as e:
        log_text = f"Could not read logs: {e}"

    # 2. Send photo if available
    photo_path = "current_screen.png"
    has_photo = os.path.exists(photo_path)
    
    if has_photo:
        url_photo = API_URL + "sendPhoto"
        try:
            with open(photo_path, 'rb') as p:
                files = {'photo': p}
                data = {'chat_id': TELEGRAM_CHAT_ID, 'caption': f"📸 Current Screen\nStatus: {bot_instance.state}\nPaused: {bot_instance.paused}"}
                requests.post(url_photo, data=data, files=files, timeout=30)
        except Exception as e:
            logger.error(f"Failed to send photo: {e}")
            
    # Send Logs
    url_msg = API_URL + "sendMessage"
    
    # Escape HTML special characters for the <pre> block just in case
    escaped_logs = log_text.replace('<', '&lt;').replace('>', '&gt;')
    
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": f"📋 <b>Last 10 Logs</b>\n<pre>{escaped_logs[-3000:]}</pre>",
        "parse_mode": "HTML",
        "reply_markup": {
            "keyboard": [[{"text": "/status"}, {"text": "/loot"}], [{"text": "/pause"}, {"text": "/resume"}], [{"text": "/restart"}, {"text": "/device"}]],
            "resize_keyboard": True
        }
    }
    try:
        requests.post(url_msg, json=payload, timeout=5)
    except Exception as e:
        logger.error(f"Failed to send status message: {e}")

def send_telegram_loot(bot_instance):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
        
    screen = bot_instance.bot.take_screenshot("current_screen.png")
    text, numbers = bot_instance.vision.read_loot(screen)
    
    if text is None:
        send_telegram_message("❌ <b>OCR Error</b>\nFailed to extract loot text.")
        return
        
    photo_path = "loot_crop.png"
    has_photo = os.path.exists(photo_path)
    
    if has_photo:
        url_photo = API_URL + "sendPhoto"
        try:
            with open(photo_path, 'rb') as p:
                files = {'photo': p}
                data = {'chat_id': TELEGRAM_CHAT_ID, 'caption': f"💰 <b>Loot Status</b>\nExtracted Text: {text}"}
                requests.post(url_photo, data=data, files=files, timeout=30)
        except Exception as e:
            logger.error(f"Failed to send loot photo: {e}")
            
    else:
        send_telegram_message(f"💰 <b>Loot Status</b>\nExtracted Text: {text}")

def poll_updates(bot_instance):
    offset = None
    while bot_instance.running:
        try:
            url = API_URL + "getUpdates"
            params = {"timeout": 30}
            if offset:
                params["offset"] = offset
            
            response = requests.get(url, params=params, timeout=40)
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    for update in data.get("result", []):
                        offset = update["update_id"] + 1
                        message = update.get("message", {})
                        text = message.get("text", "")
                        
                        if text == "/pause":
                            bot_instance.paused = True
                            logger.info("Bot paused via Telegram.")
                            send_telegram_message("⏸ <b>Bot Paused</b>\nBot operations are currently halted.")
                        elif text == "/resume":
                            bot_instance.paused = False
                            logger.info("Bot resumed via Telegram.")
                            send_telegram_message("▶️ <b>Bot Resumed</b>\nBot operations are continuing.")
                        elif text == "/status":
                            send_telegram_status(bot_instance)
                        elif text == "/loot":
                            logger.info("Loot requested via Telegram.")
                            send_telegram_loot(bot_instance)
                        elif text == "/restart":
                            send_telegram_message("🔄 <b>Restarting Bot...</b>\nRebooting the python script.")
                            logger.info("Bot restarting via Telegram.")
                            import sys
                            # Acknowledge the update to prevent infinite restart loops
                            try:
                                requests.get(API_URL + "getUpdates", params={"offset": offset}, timeout=5)
                            except Exception:
                                pass
                            os.execv(sys.executable, ['python'] + sys.argv)
                        elif text.startswith("/device"):
                            import adbutils
                            try:
                                adb = adbutils.AdbClient(host="127.0.0.1", port=5037)
                                devices = adb.device_list()
                                
                                inline_kb = {"inline_keyboard": []}
                                for i, d in enumerate(devices):
                                    inline_kb["inline_keyboard"].append([{"text": f"📱 {d.serial}", "callback_data": f"device_{d.serial}"}])
                                
                                url_msg = API_URL + "sendMessage"
                                payload = {
                                    "chat_id": TELEGRAM_CHAT_ID,
                                    "text": "📱 <b>Select an ADB Device:</b>",
                                    "parse_mode": "HTML",
                                    "reply_markup": inline_kb
                                }
                                requests.post(url_msg, json=payload, timeout=5)
                            except Exception as e:
                                send_telegram_message(f"❌ ADB Error: {e}")
                                
                        # Handle Inline Keyboard Callbacks
                        elif "callback_query" in update:
                            cq = update["callback_query"]
                            data = cq.get("data", "")
                            
                            # Answer the callback query to remove loading state
                            cq_id = cq.get("id")
                            requests.post(API_URL + "answerCallbackQuery", json={"callback_query_id": cq_id}, timeout=5)
                            
                            if data.startswith("device_"):
                                target_serial = data.split("device_")[1]
                                import adbutils
                                try:
                                    adb = adbutils.AdbClient(host="127.0.0.1", port=5037)
                                    devices = adb.device_list()
                                    
                                    target_device = None
                                    for d in devices:
                                        if d.serial == target_serial:
                                            target_device = d
                                            break
                                            
                                    if target_device:
                                        send_telegram_message(f"🔄 Switching to device: <code>{target_device.serial}</code>")
                                        bot_instance.bot.device = target_device
                                        bot_instance.bot.serial = target_device.serial
                                        bot_instance.bot._log_screen_size()
                                        if hasattr(bot_instance.vision, 'cached_scale'):
                                            bot_instance.vision.cached_scale = None
                                            bot_instance.vision.last_screen_h = None
                                        send_telegram_message("✅ Switched successfully!")
                                    else:
                                        send_telegram_message("❌ Device not found! It might have disconnected.")
                                except Exception as e:
                                    send_telegram_message(f"❌ Error switching device: {e}")
        except Exception as e:
            # Silence connection errors during polling to prevent log spam
            time.sleep(5)

def start_polling(bot_instance):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.info("Telegram credentials not found. Remote control disabled.")
        return
    logger.info("Starting Telegram Remote Control thread...")
    thread = threading.Thread(target=poll_updates, args=(bot_instance,), daemon=True)
    thread.start()
