# -*- coding: utf-8 -*-

import dbus
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

from moonboard import MoonBoard

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Test led system')

    parser.add_argument('--led_mapping', type=str,
                        help='Relative path JSON file containing the led mapping',
                        default="led_mapping.json")

    parser.add_argument('--led_test', type=bool,
                        help='Enable test of all leds',
                        default=False)

    args = parser.parse_args()

    led_controller = "PiWS281x"
    moon = MoonBoard(led_controller, args.led_mapping)

    if args.led_test:
        moon.led_layout_test(0.1)

    dbml = DBusGMainLoop(set_as_default=True)

    bus = dbus.SystemBus()
    proxy = bus.get_object('com.moonboard', '/com/moonboard')

    proxy.connect_to_signal('new_problem', moon.on_problem_reception)
    loop = GLib.MainLoop()

    dbus.set_default_main_loop(dbml)

    # Run the loop
    try:
        loop.run()
    except KeyboardInterrupt:
        print("keyboard interrupt received")
    except Exception as e:
        print("Unexpected exception occurred: '{}'".format(str(e)))
    finally:
        loop.quit()
