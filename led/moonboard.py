# -*- coding: utf-8 -*-
import json
import os
import string
import time

import dbus
from bibliopixel import Strip
from bibliopixel.colors import COLORS
from bibliopixel.drivers.PiWS281X import PiWS281X
from bibliopixel.drivers.dummy_driver import DriverDummy

import welcome_layout


class MoonBoard:
    DEFAULT_PROBLEM_COLORS = {'START': COLORS.green, 'TOP': COLORS.red, 'MOVES': COLORS.blue}
    DEFAULT_COLOR = COLORS.blue
    ROWS = 18
    COLS = 11
    DEFAULT_BRIGHTNESS = 100
    DEFAULT_LED_MAPPING_FILE = 'led_mapping.json'

    def __init__(self,
                 driver_type: str,
                 led_mapping: str = DEFAULT_LED_MAPPING_FILE,
                 brightness: int = DEFAULT_BRIGHTNESS):
        # read led mapping
        led_mapping_path = os.path.join(os.path.dirname(__file__), led_mapping)
        with open(led_mapping_path) as json_file:
            try:
                data = json.load(json_file)
            except Exception as e:
                print("Json led mapping not a valid JSON.")
                raise e
            else:
                self.MAPPING = data

        try:
            num_pixels = self.MAPPING["num_pixels"]
        except KeyError:
            num_pixels = max(self.MAPPING.values()) + 1

        try:
            if driver_type == "PiWS281x":
                driver = PiWS281X(num_pixels)
            else:
                raise ValueError(f"Unknown driver type {driver_type}")
        except Exception as e:
            print(f"Not able to initialize the driver. Error {e}")
            exit(-1)

        self.layout = Strip(driver, brightness=brightness, threadedUpdate=True)
        self.layout.cleanup_drivers()
        self.layout.start()
        self.show_welcome_layout()

    def clear(self):
        self.layout.all_off()
        self.layout.push_to_driver()

    def set_hold(self, hold: str, color=DEFAULT_COLOR):
        self.layout.set(self.MAPPING[hold], color)

    def on_problem_reception(self, holds: dbus.String):
        self.show_problem(json.loads(holds))

    def show_problem(self, holds: dict, hold_colors: dict = DEFAULT_PROBLEM_COLORS):
        self.clear()
        for k in ['START', 'MOVES', 'TOP']:
            for hold in holds.get(k, tuple()):
                self.set_hold(hold, hold_colors.get(k))

        self.layout.push_to_driver()

    def led_layout_test(self, duration: float):
        col_names = string.ascii_uppercase[0:11]

        for c in col_names:
            for j in range(1, self.ROWS + 1):
                h = c + str(j)
                print(h)
                for color in [COLORS.red, COLORS.blue]:
                    self.layout.set(self.MAPPING[h], color)
                    self.layout.push_to_driver()
                    time.sleep(duration)

        time.sleep(5)
        self.layout.push_to_driver()
        self.clear()

    def show_welcome_layout(self):
        self.clear()
        self.show_problem(welcome_layout.WELCOME_LAYOUT, welcome_layout.WELCOME_LAYOUT_COLORS)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Test led system')

    parser.add_argument('--led_mapping', type=str,
                        help='Relative path JSON file containing the led mapping.',
                        default="led_mapping.json")

    args = parser.parse_args()

    led_controller = "PiWS281x"
    moon = MoonBoard(led_controller, args.led_mapping)
