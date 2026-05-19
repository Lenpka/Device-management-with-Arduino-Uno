"""Общий Serial-клиент для CLI и GUI."""

from __future__ import annotations

import time
from typing import Callable

try:
    import serial
    from serial.tools import list_ports
except ImportError as exc:
    raise SystemExit("Установите pyserial: pip install pyserial") from exc

BAUD = 115200
BOOT_DELAY_S = 2.0
READ_TIMEOUT_S = 1.0

CHANNEL_COUNT = 8
PWM_CHANNELS = frozenset({2, 4, 5, 6, 7, 8})


def list_serial_ports() -> list[str]:
    return [p.device for p in list_ports.comports()]


def parse_stat_line(line: str) -> list[int] | None:
    if not line.startswith("STAT"):
        return None
    body = line[4:].strip()
    if not body:
        return None
    try:
        return [int(x) for x in body.split(",")]
    except ValueError:
        return None


class ArduinoChannelClient:
    def __init__(self, port: str) -> None:
        self.port = port
        self._ser = serial.Serial(port, BAUD, timeout=READ_TIMEOUT_S)
        time.sleep(BOOT_DELAY_S)
        self._ser.reset_input_buffer()

    def close(self) -> None:
        if self._ser.is_open:
            self._ser.close()

    @property
    def is_open(self) -> bool:
        return self._ser.is_open

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
                if text.startswith(("ACK", "ERR", "STAT")):
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

    def all_off(self) -> list[str]:
        lines: list[str] = []
        for ch in range(1, CHANNEL_COUNT + 1):
            lines.extend(self.set_channel(ch, 0))
        return lines


class ChannelController:
    def __init__(
        self,
        on_log: Callable[[str], None],
        on_stat: Callable[[list[int]], None],
        on_connected: Callable[[bool], None],
    ) -> None:
        self._on_log = on_log
        self._on_stat = on_stat
        self._on_connected = on_connected
        self._client: ArduinoChannelClient | None = None

    @property
    def connected(self) -> bool:
        return self._client is not None and self._client.is_open

    def _handle_replies(self, replies: list[str]) -> None:
        for line in replies:
            self._on_log(line)
            levels = parse_stat_line(line)
            if levels is not None:
                self._on_stat(levels)

    def connect(self, port: str, worker: "UiWorker") -> None:
        def task() -> None:
            try:
                self._client = ArduinoChannelClient(port)
                worker.post(lambda: self._on_connected(True))
                worker.post(lambda: self._handle_replies(self._client.get_status()))
            except Exception as exc:
                self._client = None
                worker.post(lambda: self._on_log(f"Ошибка подключения: {exc}"))
                worker.post(lambda: self._on_connected(False))

        worker.run_bg(task)

    def disconnect(self) -> None:
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None
        self._on_connected(False)

    def _require_client(self) -> ArduinoChannelClient:
        if not self.connected or self._client is None:
            raise RuntimeError("Нет подключения к Arduino")
        return self._client

    def _run(self, worker: "UiWorker", fn: Callable[[], list[str]]) -> None:
        def task() -> None:
            try:
                replies = fn()
                worker.post(lambda: self._handle_replies(replies))
            except Exception as exc:
                worker.post(lambda: self._on_log(f"Ошибка: {exc}"))

        if not self.connected:
            self._on_log("Сначала подключитесь к порту")
            return
        worker.run_bg(task)

    def set_on(self, ch: int, worker: "UiWorker") -> None:
        self._run(worker, lambda: self._require_client().set_channel(ch, 1))

    def set_off(self, ch: int, worker: "UiWorker") -> None:
        self._run(worker, lambda: self._require_client().set_channel(ch, 0))

    def set_freq(self, ch: int, hz: int, worker: "UiWorker") -> None:
        self._run(worker, lambda: self._require_client().set_frequency(ch, hz))

    def set_pwm(self, ch: int, duty: int, worker: "UiWorker") -> None:
        self._run(worker, lambda: self._require_client().set_pwm(ch, duty))

    def refresh_stat(self, worker: "UiWorker") -> None:
        self._run(worker, lambda: self._require_client().get_status())

    def all_off(self, worker: "UiWorker") -> None:
        self._run(worker, lambda: self._require_client().all_off())
