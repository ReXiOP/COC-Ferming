import colorama
from colorama import Fore, Style
import time

def print_banner():
    colorama.init()
    banner = f"""
{Fore.CYAN}{Style.BRIGHT}
  ____ _           _       ____        _   
 / ___| | __ _ ___| |__   | __ )  ___ | |_ 
| |   | |/ _` / __| '_ \  |  _ \ / _ \| __|
| |___| | (_| \__ \ | | | | |_) | (_) | |_ 
 \____|_|\__,_|___/_| |_| |____/ \___/ \__|
{Style.RESET_ALL}
{Fore.GREEN}        Farming Bot - Auto Attacker{Style.RESET_ALL}
{Fore.MAGENTA}{Style.BRIGHT}                Created by Sajid{Style.RESET_ALL}
{Fore.YELLOW}=============================================={Style.RESET_ALL}
"""
    print(banner)
    time.sleep(1)
