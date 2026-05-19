#!/usr/bin/env python3
"""
CLI-клиент выходных каналов CH1..CH8 (Arduino UNO + ULN2803A).
Требования: pip install pyserial
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from arduino_client import ArduinoChannelClient
except ImportError:
    print("Запускайте из каталога python/ или установите pyserial", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Управление выходными каналами CH1..CH8 (ULN2803) по Serial"
    )
    parser.add_argument("port", help="COM-порт, например COM3 или /dev/ttyUSB0")
    sub = parser.add_subparsers(dest="action", required=True)

    p_on = sub.add_parser("on", help="SET: включить выходной канал CH")
    p_on.add_argument("channel", type=int, metavar="CH")
    p_off = sub.add_parser("off", help="SET: выключить выходной канал CH")
    p_off.add_argument("channel", type=int, metavar="CH")

    p_freq = sub.add_parser("freq", help="FREQ: меандр на любом CH, Гц (0 = стоп)")
    p_freq.add_argument("channel", type=int, metavar="CH")
    p_freq.add_argument("hz", type=int)

    p_pwm = sub.add_parser(
        "pwm",
        help="PWM: analogWrite 0..255 только CH2,4,5,6,7,8",
    )
    p_pwm.add_argument("channel", type=int, metavar="CH")
    p_pwm.add_argument("duty", type=int)

    sub.add_parser("stat", help="GET: один ответ STAT (логика на пинах)")
    sub.add_parser("monitor", help="GET: периодический STAT")

    args = parser.parse_args()
    client = ArduinoChannelClient(args.port)
    try:
        if args.action == "on":
            replies = client.set_channel(args.channel, 1)
        elif args.action == "off":
            replies = client.set_channel(args.channel, 0)
        elif args.action == "freq":
            replies = client.set_frequency(args.channel, args.hz)
        elif args.action == "pwm":
            replies = client.set_pwm(args.channel, args.duty)
        elif args.action == "stat":
            replies = client.get_status()
        elif args.action == "monitor":
            import time

            print("Опрос логического STAT (Ctrl+C для выхода):")
            try:
                while True:
                    for line in client.get_status():
                        print(line)
                    time.sleep(0.5)
            except KeyboardInterrupt:
                print("\nОстановлено.")
            return
        else:
            replies = []
        for line in replies:
            print(line)
    finally:
        client.close()


if __name__ == "__main__":
    main()
