import os
import time
import subprocess
import logging
from logging.handlers import RotatingFileHandler
import time
from pwnagotchi.ui.hw.libs.waveshare.epaper.v2in13_V4.epd2in13_V4 import EPD
from PIL import Image, ImageDraw, ImageFont
import pwnagotchi.ui.fonts as fonts
import toml
import sys
import random

epd = EPD()
epd.init()

# setup logging
verbose_log_file = os.path.join(os.getcwd(), 'stealth_worker.log')
pwnagotchi_log_file = '/etc/pwnagotchi/log/pwnagotchi.log'
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create handlers and configure them
# Verbose log file handler
verbose_handler = RotatingFileHandler(verbose_log_file, maxBytes=1024*1024, backupCount=5)  # Rotate log files when they reach 1 MB
verbose_handler.setLevel(logging.INFO)
verbose_formatter = logging.Formatter('[%(asctime)s.%(msecs)03d] [%(levelname)s] [stealth_worker] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
verbose_handler.setFormatter(verbose_formatter)

# Pwnagotchi log file handler (less verbose)
pwnagotchi_handler = logging.FileHandler(pwnagotchi_log_file)
pwnagotchi_handler.setLevel(logging.WARNING)  # Only log warnings and above
pwnagotchi_formatter = logging.Formatter('[%(asctime)s.%(msecs)03d] [%(levelname)s] [stealth_worker] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
pwnagotchi_handler.setFormatter(pwnagotchi_formatter)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('[%(asctime)s.%(msecs)03d] [%(levelname)s] [stealth_worker] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
console_handler.setFormatter(console_formatter)

# Add handlers to the logger
logger.addHandler(verbose_handler)
logger.addHandler(pwnagotchi_handler)
logger.addHandler(console_handler)

def exec_cmd(cmd):
    try:
        result = subprocess.run(cmd, shell=True, stdin=None, stderr=subprocess.PIPE, stdout=subprocess.PIPE, executable="/bin/bash")
        output = result.stdout.decode('utf-8') + result.stderr.decode('utf-8')
        if result.returncode == 0:
            logger.info(f"{cmd} : Exit code {result.returncode}")
        else:
            if (result.returncode == 3):
                logger.warning("pwnagotchi service was already stopped.")
            else:
                logger.error(f"{cmd} : Exit code {result.returncode}. Error: {result.stderr.decode('utf-8')}")
        logger.info(output)
        return output
    except OSError as e:
        logger.error(f"Failed to execute command '{cmd}': {e}")
        return str(e)

def ssid_strength(ssid):
    iwlist_output = exec_cmd("sudo iwlist wlan0 scan | egrep 'ESSID|Signal level'")
    if ("Network is down" in iwlist_output):
        logger.error(f"wlan0 down. Terminating stealth_worker.")
        sys.exit()
    networks = iwlist_output.strip().split("\n")
    
    for i in range(0, len(networks), 2):
        if i + 1 >= len(networks):
            break

        essid_line = networks[i + 1].strip()
        signal_line = networks[i].strip()
        if (ssid in essid_line):
            signal_level = int(signal_line.split('Signal level=')[1].replace(' dBm', ''))
            return signal_level
    return -100
    
def draw_image(image_path):
    # Initialize the EPD
    epd = EPD()
    epd.init()
    epd.Clear()

    # Open the image file
    image = Image.open(image_path)

    display_width = epd.width
    display_height = epd.height
    
    resized_image = image.resize((display_width, display_height))
    bw_image = resized_image.convert('1')

    epd.display(epd.getbuffer(bw_image))

def draw_image_with_text(image_path, text):
    # Initialize the EPD
    #epd = EPD()
    #epd.init()
    #epd.Clear()

    # Open the image file
    image = Image.open(image_path)

    display_width = epd.width
    display_height = epd.height
    
    resized_image = image.resize((display_width, display_height))
    bw_image = resized_image.convert('1')
    
    # Create a drawing context
    draw = ImageDraw.Draw(bw_image)

    # Load the font
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf', 24)

    # Calculate the size of the text
    text_width, text_height = draw.textsize(text, font)

    # Calculate the position to center the text
    x = (display_width - text_width) // 2
    y = (display_height - text_height) // 2

    # Draw a white background rectangle for the text
    background_margin = 5
    background_coords = [(x - background_margin, y - background_margin),
                         (x + text_width + background_margin, y + text_height + background_margin)]
    draw.rectangle(background_coords, fill=255)

    # Draw the text
    draw.text((x, y), text, font=font, fill=0)

    epd.display(epd.getbuffer(bw_image))

def get_image_paths(folder_path):
    return [os.path.join(root, file)
            for root, _, files in os.walk(folder_path)
            for file in files
            if file.lower().endswith(('.png', '.jpeg', '.jpg'))]

if __name__ == '__main__':
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Check if the script is being run with sudo permissions
    if os.geteuid() == 0:
        logger.info("stealth_worker.py is running with sudo permissions.")
    else:
        logger.warning("stealth_worker.py is running without sudo permissions.")

    config_file = '/etc/pwnagotchi/config.toml'
    with open(config_file, 'r') as file:
        config = toml.load(file)
    
    # The ssid to stealth around. While this ssid is around, we will busy wait 
    ssid = config['main']['plugins']['stealth_base']['ssid']
    # Number of times we can go out of range of the ssid before exiting
    missNum = config['main']['plugins']['stealth_base'].get('missNum', 3)
    # The directory that houses all the images you'd like to display
    imageDir = config['main']['plugins']['stealth_base'].get('imageDir', '/usr/local/share/pwnagotchi/installed-plugins/stealth_base_photos')
    # The lowest singnal strength allowed before we consider te ssid out of range
    minimum_signal_strength = int(config['main']['plugins']['stealth_base'].get('minimum_signal_strength', -60))
    # In seconds, how often we check to see if our target ssid is in range
    ssid_check_interval = config['main']['plugins']['stealth_base'].get('ssid_check_interval', 5)
    # In seconds, how often we refresh the screen with a new image
    screen_refresh_interval = config['main']['plugins']['stealth_base'].get('screen_refresh_interval', 30)

    logger.info(f"Read config valules: " + 
       "\n\tmain.plugins.stealth_base.ssid: {ssid}, " + 
       "\n\tmain.plugins.stealth_base.missNum: {missNum}, " + 
       "\n\tmain.plugins.stealth_base.imageDir: {imageDir}, " + 
       "\n\tmain.plugins.stealth_base.minimum_signal_strength: {minimum_signal_strength}, " + 
       "\n\tmain.plugins.stealth_base.ssid_check_interval: {ssid_check_interval}, " + 
       "\n\tmain.plugins.stealth_base.screen_refresh_interval: {screen_refresh_interval}, ")

    # stop pwnagotchi service
    logger.warning("Stopping pwnagotchi service")
    logger.info(exec_cmd("systemctl stop pwnagotchi"))
    logger.info(exec_cmd("sudo systemctl status pwnagotchi"))
    
    # bring wlan0 up
    logger.info(exec_cmd("sudo ifconfig wlan0 up"))
    logger.info(exec_cmd("ifconfig"))
    
    # while we are in range of our ssid, busy wait
    last_ssid_check_time = time.time()
    last_screen_refresh_time = time.time()
    images = get_image_paths(imageDir)
    random.shuffle(images)
    imgIndex = 0
    # missNum used in case connection strength is straddling minimum_signal_strength
    while missNum > 0:
        current_time = time.time()

        # Check if it's time to get the SSID strength
        if current_time - last_ssid_check_time >= ssid_check_interval:
            strength = ssid_strength(ssid)
            logger.info(f"{ssid} : {strength} < {minimum_signal_strength} = {strength < minimum_signal_strength}")
            if strength < minimum_signal_strength:
                missNum -= 1
                logger.warning(f"{missNum} attempts remaining for {ssid} : {strength}/{minimum_signal_strength}")
            else:
                missNum = config['main']['plugins']['stealth_base'].get('missNum', 3)
            last_ssid_check_time = current_time

        # Check if it's time to refresh the screen. Can chaneg this to do anything you'd like.
        if current_time - last_screen_refresh_time >= screen_refresh_interval:
            try:
                imgIndex = (imgIndex + 1) % len(images)
                draw_image_with_text(images[imgIndex], f"{strength}")
            except Exception as e:
                logger.error(f"Error while drawing image: {e}")
            last_screen_refresh_time = current_time

        time.sleep(0.1)
    
    # bring wlan0 down
    logger.info(exec_cmd("sudo ifconfig wlan0 down"))
    logger.info(exec_cmd("ifconfig"))
    
    # start pwnagotchi service
    logger.warning("Starting pwnagotchi service")
    logger.info(exec_cmd("systemctl start pwnagotchi"))
    logger.info(exec_cmd("sudo systemctl status pwnagotchi"))
    

