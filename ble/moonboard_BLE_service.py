import json
import logging
import os
import pty
import subprocess
import sys
import threading

import dbus
import dbus.mainloop.glib
from gi.repository import GLib

import gatt_base.gatt_lib_variables as gatt_var
from gatt_base.gatt_lib_characteristic import Characteristic
from gatt_base.gatt_lib_service import Service
from moonboard_app_protocol import UnstuffSequence, decode_problem_string

UART_SERVICE_UUID =             '6e400001-b5a3-f393-e0a9-e50e24dcca9e'
UART_RX_CHARACTERISTIC_UUID =   '6e400002-b5a3-f393-e0a9-e50e24dcca9e'
UART_TX_CHARACTERISTIC_UUID =   '6e400003-b5a3-f393-e0a9-e50e24dcca9e'

LOCAL_NAME      = 'Moonboard ElCapitan'
SERVICE_NAME    = 'com.moonboard'
LOGGER_NAME     = 'moonboard'


# NOTE Sometimes the second part of packet is lost. Therefore btmon is used
class RxCharacteristic(Characteristic):
    def __init__(self, bus, index, service, process_rx):
        Characteristic.__init__(self, bus, index, UART_RX_CHARACTERISTIC_UUID, ['write'], service)
        self.process_rx = process_rx

    @dbus.service.method(gatt_var.GATT_CHRC_IFACE, in_signature='aya{sv}')
    def WriteValue(self, value, options):
        pass
        self.process_rx(value)


class UartService(Service):
    def __init__(self, bus, path, index, process_rx):
        Service.__init__(self, bus, path, index, UART_SERVICE_UUID, True)
        self.add_characteristic(RxCharacteristic(bus, 1, self, process_rx))


class DataStream:
    def __init__(self, fileno: int):
        self._fileno: int = fileno
        self._buffer: bytes = b""

    def read_lines(self):
        try:
            output = os.read(self._fileno, 1000)
        except OSError as e:
            if e.errno != errno.EIO:
                raise

            output = b""

        lines = output.split(b"\n")
        lines[0] = self._buffer + lines[0]  # prepend previous
        # non-finished line.
        if output:
            self._buffer = lines[-1]
            finished_lines = lines[:-1]
            readable = True
        else:
            self._buffer = b""
            if len(lines) == 1 and not lines[0]:
                # We did not have buffer left, so no output at all.
                lines = []
            finished_lines = lines
            readable = False

        finished_lines = [line.rstrip(b"\r") for line in finished_lines]

        return finished_lines, readable


class MoonApplication(dbus.service.Object):
    IFACE = "com.moonboard.method"
    PATH = '/com/moonboard'

    def __init__(self, bus: dbus.service.BusName, logger: logging.Logger):
        super().__init__(bus, self.PATH)

        self.services = []
        self.logger = logger
        self.unstuffer = UnstuffSequence(self.logger)

        self.add_service(UartService(bus, self.get_path(), 0, self.process_rx))

        monitor_thread = threading.Thread(target=self.monitor_btmon)
        monitor_thread.start()

    def monitor_btmon(self):
        out_r, out_w = pty.openpty()
        cmd = ["sudo", "btmon"]
        subprocess.Popen(cmd, stdout=out_w)

        f = DataStream(out_r)
        while True:
            lines, readable = f.read_lines()
            if not readable:
                break

            for line in lines:
                if line == '':
                    continue

                line = line.decode()
                if 'Data:' in line:
                    data = line.replace(' ', '').replace('\x1b', '').replace('[0m', '').replace('Data:', '')
                    self.logger.info('New data ' + data)
                    self.process_rx(data)

    def process_rx(self, ba):
        new_problem_string = self.unstuffer.process_bytes(ba)
        flags = self.unstuffer.flags

        if new_problem_string is not None:
            problem = decode_problem_string(new_problem_string, flags)
            self.new_problem(json.dumps(problem))
            self.unstuffer.reset()
            start_adv(self.logger)

    @dbus.service.signal(dbus_interface="com.moonboard", signature="s")
    def new_problem(self, problem: str):
        self.logger.info('Signal new problem: ' + str(problem))

    def get_path(self):
        return dbus.ObjectPath(self.PATH)

    def add_service(self, service):
        self.services.append(service)

    @dbus.service.method(gatt_var.DBUS_OM_IFACE, out_signature='a{oa{sa{sv}}}')
    def GetManagedObjects(self):
        response = {}
        for service in self.services:
            response[service.get_path()] = service.get_properties()
            chrcs = service.get_characteristics()
            for chrc in chrcs:
                response[chrc.get_path()] = chrc.get_properties()
        return response


def run(*popenargs, **kwargs):
    process = subprocess.Popen(*popenargs, **kwargs)

    try:
        stdout, stderr = process.communicate()
    except Exception:
        process.kill()
        process.wait()
        raise

    retcode = process.poll()

    return retcode, stdout, stderr


def setup_adv(logger: logging.Logger):
    logger.info('setup adv')

    setup_adv_commands = [
        "hcitool -i hci0 cmd 0x08 0x000a 00",
        "hcitool -i hci0 cmd 0x08 0x0008 18 02 01 06 02 0a 00 11 07 9e ca dc 24 0e e5 a9 e0 93 f3 a3 b5 01 00 40 6e 00 00 00 00 00 00 00",
        "hcitool -i hci0 cmd 0x08 0x0009 0d 0c 09 4d 6f 6f 6e 62 6f 61 72 64 20 41",
        "hcitool -i hci0 cmd 0x08 0x0006 80 02 c0 03 00 00 00 00 00 00 00 00 00 07 00"
    ]

    for c in setup_adv_commands:
        run("sudo " + c, shell=True)


def start_adv(logger, start=True):
    if start:
        start = '01'
        logger.info('start adv')
    else:
        start = '00'
        logger.info('stop adv')

    start_adv_command = f"hcitool -i hci0 cmd 0x08 0x000a {start}"

    run("sudo " + start_adv_command, shell=True)


def main(logger: logging.Logger, adapter: str):
    logger.info("Bluetooth adapter: " + str(adapter))

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()

    try:
        bus_name = dbus.service.BusName(SERVICE_NAME, bus=bus, do_not_queue=True)
    except dbus.exceptions.NameExistsException:
        logger.critical(f"Bus name {SERVICE_NAME} already exists")
        sys.exit(1)

    app = MoonApplication(bus_name, logger)

    service_manager = dbus.Interface(bus.get_object(gatt_var.BLUEZ_SERVICE_NAME, adapter), gatt_var.GATT_MANAGER_IFACE)

    loop = GLib.MainLoop()

    logger.info('app path: ' + app.get_path())

    service_manager.RegisterApplication(app.get_path(), {},
                                        reply_handler=lambda: print("GATT application registered"),
                                        error_handler=lambda error: print(f"Failed to register application: {error}"))

    setup_adv(logger)
    start_adv(logger, True)

    # Run the loop
    try:
        loop.run()
    except KeyboardInterrupt:
        print("Keyboard interrupt received")
    except Exception as e:
        print("Unexpected exception occurred: '{}'".format(str(e)))
    finally:
        loop.quit()


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Moonboard bluetooth service')
    parser.add_argument('--debug', action="store_true")

    args = parser.parse_args()

    moon_logger = logging.getLogger(LOGGER_NAME)
    moon_logger.addHandler(logging.StreamHandler())

    if args.debug:
        moon_logger.setLevel(logging.DEBUG)
    else:
        moon_logger.setLevel(logging.INFO)

    main(moon_logger, adapter='/org/bluez/hci0')
