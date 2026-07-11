import logging
import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

# Create logs directory
if not os.path.exists('logs'):
    os.makedirs('logs')

# Create a custom logger
logger = logging.getLogger('CocBot')
logger.setLevel(logging.DEBUG)

# Create handlers
c_handler = logging.StreamHandler(sys.stdout)
f_handler = logging.FileHandler('logs/bot.log')
c_handler.setLevel(logging.INFO)
f_handler.setLevel(logging.INFO)

# Create formatters and add it to handlers
c_format = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s', datefmt='%H:%M:%S')
f_format = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s')

c_handler.setFormatter(c_format)
f_handler.setFormatter(f_format)

# Add handlers to the logger
logger.addHandler(c_handler)
logger.addHandler(f_handler)

# Telegram Handler for errors
class TelegramHandler(logging.Handler):
    def __init__(self, token, chat_id):
        super().__init__()
        self.token = token
        self.chat_id = chat_id

    def emit(self, record):
        try:
            msg = self.format(record)
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": msg,
                "parse_mode": "HTML"
            }
            requests.post(url, json=payload, timeout=5)
        except Exception:
            self.handleError(record)

telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")

if telegram_token and telegram_chat_id:
    t_handler = TelegramHandler(telegram_token, telegram_chat_id)
    t_handler.setLevel(logging.ERROR)
    # Using HTML pre tag so stack traces format correctly in Telegram
    t_format = logging.Formatter('🚨 <b>CocBot Error</b> 🚨\n<pre>%(message)s</pre>')
    t_handler.setFormatter(t_format)
    logger.addHandler(t_handler)

def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = handle_exception
