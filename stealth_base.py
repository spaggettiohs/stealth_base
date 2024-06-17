import pwnagotchi.plugins as plugins
import pwnagotchi
import logging
import subprocess
import time
import os

class StealthBase(plugins.Plugin):
    __author__ = ''
    __version__ = '1.0.0'
    __license__ = 'GPL3'
    __description__ = 'Shuts off when near specified network'

    def __init__(self):
        self.tag = "[stealth_base]"
        self.ready = 0
        self.status = ''
        self.network = ''
        self.stealth_found = False
        self.worker_running = False

    def on_loaded(self):
        logger.info(f"Read config valules: " + 
       "\n\tmain.plugins.stealth_base.ssid: {ssid}, " + 
       "\n\tmain.plugins.stealth_base.missNum: {missNum}, " + 
       "\n\tmain.plugins.stealth_base.imageDir: {imageDir}, " + 
       "\n\tmain.plugins.stealth_base.minimum_signal_strength: {minimum_signal_strength}, " + 
       "\n\tmain.plugins.stealth_base.ssid_check_interval: {ssid_check_interval}, " + 
       "\n\tmain.plugins.stealth_base.screen_refresh_interval: {screen_refresh_interval}, ")
       
        for opt in ['ssid', 'minimum_signal_strength', 'worker_script']:
            if opt not in self.options or (opt in self.options and self.options[opt] is None):
                logging.error(f"{self.tag} Option {opt} is not set.")
                return
        self.worker_script = os.path.abspath(self.options['worker_script'])
        self.network = self.options['ssid']
        self.ready = 1
        logging.info("{self.tag} plugin loaded")
        
    
    def on_unfiltered_ap_list(self, agent, access_points):
        logging.info(f"{self.tag} on_unfiltered_ap_list self.ready: {self.ready}")
        if self.ready == 1:
            self.stealth_found = False
            for network in access_points:
                if network['hostname'] == self.network:
                    self.stealth_found = True
                    signal_strength = network['rssi']
                    channel = network['channel']
                    logging.info("{self.tag} FOUND stealth network nearby on channel %d (rssi: %d)" % (channel, signal_strength))
                    if signal_strength >= self.options['minimum_signal_strength']:
                        logging.info("{self.tag} Strength threshold hit...")
                        self.status = 'stealth'
                    else:
                        logging.info("{self.tag} The signal strength is too low (%d) to connect." % (signal_strength))
                        self.status = 'rssi_low'

    def on_ui_update(self, ui):
        if self.status == 'rssi_low':
            ui.set('face', '(⌐■_■)')
            ui.set('status', 'I can see %s on the horizon.' % self.network)
            logging.info(f"{self.tag} rssi_low")
        if self.status == 'stealth' and self.worker_running == False:
            logging.info(f"{self.tag} Starting script: {self.worker_script}")
            try:
                # Start the worker service
                cmd = "sudo systemctl start stealth_worker.service"
                result = subprocess.run(cmd, shell=True, stdin=None, stderr=subprocess.PIPE, stdout=subprocess.PIPE, executable="/bin/bash")
                output = result.stdout.decode('utf-8') + result.stderr.decode('utf-8')
                if result.returncode == 0:
                    logging.info(f"{self.tag} {cmd} : Exit code {result.returncode}")
                else:
                    logging.error(f"{self.tag} {cmd} : Exit code {result.returncode}. Error: {result.stderr.decode('utf-8')}")
                logging.info(output)
                self.worker_running = True
            except OSError as e:
                logging.error(f"{self.tag} Failed to start {self.worker_script} process: {e}")
       
    def _log(message):
        logging.info('{self.tag} %s' % message)















