#!/usr/bin/env python3
"""
Клиент управления 8 выходными каналами CH1..CH8 (Arduino UNO + ULN2803A).
Требования: pip install pyserial
"""

from __future__ import annotations

import argparse
import sys
import time

try:
    import serial
except ImportError:
    print("Установите pyserial: pip install pyserial", file=sys.stderr)
    sys.exit(1)


BAUD = 115200
BOOT_DELAY_S = 2.0
READ_TIMEOUT_S = 1.0


class ArduinoChannelClient:
    def __init__(self, port: str) -> None:
        self._ser = serial.Serial(port, BAUD, timeout=READ_TIMEOUT_S)
        time.sleep(BOOT_DELAY_S)
        self._ser.reset_input_buffer()

    def close(self) -> None:
        self._ser.close()

    def _send_line(self, line: str) -> list[str]:
        payload = (line.strip() + "\n").encode("ascii")
        self._ser.write(payload)
        self._ser.flush()
        replies: list[str] = []
        deadline = time.monotonic() + READ_TIMEOUT_S
        while time.monotonic() < deadline:
            raw = self._ser.readline()
            if not raw:
                continue
            text = raw.decode("ascii", errors="replace").strip()
            if text:
                replies.append(text)
                if text.startswith("ACK") or text.startswith("ERR") or text.startswith("STAT"):
                    break
        return replies

    def set_channel(self, channel: int, state: int) -> list[str]:
        return self._send_line(f"SET {channel} {state}")

    def set_frequency(self, channel: int, hz: int) -> list[str]:
        return self._send_line(f"FREQ {channel} {hz}")

    def set_pwm(self, channel: int, duty: int) -> list[str]:
        return self._send_line(f"PWM {channel} {duty}")

    def get_status(self) -> list[str]:
        return self._send_line("GET")

    def poll_status_loop(self, interval_s: float = 0.5) -> None:
        print("Опрос логического STAT (Ctrl+C для выхода):")
        try:
            while True:
                for line in self.get_status():
                    print(line)
                time.sleep(interval_s)
        except KeyboardInterrupt:
            print("\nОстановлено.")


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
            client.poll_status_loop()
            return
        else:
            replies = []
        for line in replies:
            print(line)
    finally:
        client.close()


if __name__ == "__main__":
    main()
