#!/usr/bin/python
# -*- coding: utf-8 -*-

import argparse
import json

# import Yoctopuce library
from yoctopuce.yocto_relay import *
from yoctopuce.yocto_carbondioxide import *


class VeluxZone(object):

    def __init__(self, zonename, descr, hwid_up, hwid_down):
        self.name = zonename
        self._desription = descr
        self._upRelay = YRelay.FindRelay(hwid_up)
        self._downRelay = YRelay.FindRelay(hwid_down)

    def open(self):
        self._downRelay.pulse(200)

    def close(self):
        self._upRelay.pulse(200)

    def check_relays(self):
        if not self._upRelay.isOnline():
            sys.exit("Relay %s for zone %s is not online" % (self._desription, self._upRelay.describe()))
        if not self._downRelay.isOnline():
            sys.exit("Relay %s for zone %s is not online" % (self._desription, self._downRelay.describe()))

    def bind(self):
        self._upRelay.pulse(1300)
        pass


class VeluxControler(object):
    def __init__(self, config_file, targets, verbose):
        self.closed = True
        self.co2_open_limit = 900
        self.co2_close_limit = 700
        self.verbose = verbose
        with open('config.json', "r") as f:
            config = json.load(f)

        self.co2_open_limit = config['co2']['limit']
        self.co2_close_limit = config['co2']['limit'] - 100

        if self.verbose:
            print("Use Yoctopuce library : " + YAPI.GetAPIVersion())
        errmsg = YRefParam()
        for hub in config['yoctohubs']:
            if YAPI.RegisterHub(hub, errmsg) != YAPI.SUCCESS:
                sys.exit("Unable connect to %s : %s" % (hub, errmsg.value))

        self.co2sensor = YCarbonDioxide.FirstCarbonDioxide()
        if self.co2sensor is None:
            sys.exit("No C02 sensor found. Please plug an Yocto-CO2 or Yocto-CO2-V2 on an USB port")

        self.zones = []

        include_all_zone = False
        if len(targets) == 0 or targets[0] == "All":
            include_all_zone = True

        for zone_name in config['zones']:
            z = config['zones'][zone_name]
            if zone_name in targets or include_all_zone:
                zone = VeluxZone(zone_name, z['descr'], z['up_relay'], z['down_relay'])
                zone.check_relays()
                self.zones.append(zone)

        if self.verbose:
            msg = "Targeted zones:"
            for r in self.zones:
                msg += " " + r.name
            print(msg)

    def open(self):
        for z in self.zones:
            z.open()
            YAPI.Sleep(500)

    def close(self):
        for z in self.zones:
            z.close()
            YAPI.Sleep(500)

    def auto(self):
        if self.verbose:
            print("Co2 limit is set to %d ppm" % self.co2_open_limit)
        self.close()
        self.closed = True
        sleep_delay = 5000
        while self.co2sensor.isOnline():
            value = self.co2sensor.get_currentValue()
            if self.verbose:
                print("C02 value: %dppm" % value)
            if value > self.co2_open_limit:
                # speed up C02 measure when the windows are open
                sleep_delay = 5000  # 5 seconds
                if self.closed:
                    print("C02 concentrations (%dppm) is beyond the %dppm limit: open the windows" %
                          (value, self.co2_open_limit))
                    self.open()
                    self.closed = False
            elif value < self.co2_close_limit:
                sleep_delay = 60000  # 1 minute
                if not self.closed:
                    self.close()
                    self.closed = True
            YAPI.Sleep(sleep_delay)
        if not self.closed:
            self.close()

    def bind(self):
        z = self.zones[0]
        if self.verbose:
            print("Bind %s" % z.name)
        z.bind()

    def release(self):
        YAPI.FreeAPI()

    def read_co2(self):
        print("Co2 sensor:")
        print("  Current: %d ppm" % self.co2sensor.get_currentValue())
        print("  Min    : %d ppm" % self.co2sensor.get_lowestValue())
        print("  Max    : %d ppm" % self.co2sensor.get_highestValue())

    def reset_min_max(self):
        value = self.co2sensor.get_currentValue()
        self.co2sensor.set_highestValue(value)
        self.co2sensor.set_lowestValue(value)


def main():
    parser = argparse.ArgumentParser(description='Controller for a Velux KLF 200.')
    parser.add_argument("-v", "--verbose", help="increase output verbosity",
                        action="store_true")
    parser.add_argument('-c', '--config', default='config.json',
                        help='Config files in JSON format')
    parser.add_argument("--reset_min_max", help="reset min an max value of C02 sensor",
                        action="store_true")
    parser.add_argument('command', help="the command to execute\n Supported commandes are open/close/bind/co2")
    parser.add_argument('--zone', help="the name of the zone used. If not specified command are executed on all zones",
                        default=[], action='append')
    args = parser.parse_args()
    print(args)
    controller = VeluxControler(args.config, args.zone, args.verbose)
    if (args.reset_min_max):
        controller.reset_min_max()

    if args.command == 'open':
        controller.open()
    elif args.command == 'close':
        controller.close()
    elif args.command == 'auto':
        controller.auto()
    elif args.command == 'co2':
        controller.read_co2()
    elif args.command == 'bind':
        input("Press the config button on the Velux Remote\nPress Press Enter to continue...")
        input(
            "Press the reset button on the KLF 200 for 1 second.\nThe Led should be flashing white\nPress Press Enter to continue...")
        controller.bind()
    controller.release()


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    main()
