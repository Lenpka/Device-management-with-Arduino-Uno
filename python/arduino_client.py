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

# Подсказки для авто-выбора порта Arduino / USB-UART (CH340, CP2102, FTDI…)
ARDUINO_PORT_HINTS = (
    "arduino",
    "ch340",
    "ch341",
    "cp210",
    "ftdi",
    "usb-serial",
    "usb serial",
    "wch",
    "1a86",
    "10c4",
    "0403",
    "2341",  # Arduino VID
    "serial",
    "uno",
    "mega",
    "nano",
)


class SerialPortInfo:
    __slots__ = ("device", "description", "hwid", "label")

    def __init__(self, device: str, description: str, hwid: str) -> None:
        self.device = device
        self.description = description
        self.hwid = hwid
        self.label = f"{device} — {description}"


def _com_sort_key(device: str) -> tuple[int, int | str]:
    import re

    match = re.search(r"COM(\d+)", device, re.IGNORECASE)
    if match:
        return (0, int(match.group(1)))
    return (1, device)


def is_port_available(device: str, probe_timeout: float = 0.12) -> bool:
    """
    Порт есть в системе?
    - открывается → да;
    - «Access is denied» / занят → да (не переключать на другой COM);
    - «could not find» / нет устройства → нет (USB отключён).
    """
    try:
        ser = serial.Serial(device, baudrate=BAUD, timeout=probe_timeout)
        ser.close()
        return True
    except serial.SerialException as exc:
        msg = str(exc).lower()
        if any(
            token in msg
            for token in (
                "access is denied",
                "permission",
                "busy",
                "in use",
                "отказано",
                "занят",
            )
        ):
            return True
        if any(
            token in msg
            for token in (
                "could not open port",
                "file not found",
                "no such file",
                "cannot find",
                "не найден",
            )
        ):
            return False
        return False
    except OSError as exc:
        if getattr(exc, "errno", None) in (13, 16):
            return True
        if getattr(exc, "errno", None) in (2,):
            return False
        return False
    except ValueError:
        return False


def list_serial_port_infos(*, only_available: bool = False) -> list[SerialPortInfo]:
    """COM-порты из системы; only_available=True — только открываемые сейчас."""
    result: list[SerialPortInfo] = []
    try:
        found = list_ports.comports(include_links=True)
    except TypeError:
        found = list_ports.comports()

    for port in found:
        device = (port.device or "").strip()
        if not device:
            continue
        if only_available and not is_port_available(device):
            continue
        desc = (port.description or "Serial").strip()
        result.append(SerialPortInfo(device, desc, (port.hwid or "").strip()))

    result.sort(key=lambda item: _com_sort_key(item.device))
    return result


def list_serial_ports() -> list[str]:
    return [item.device for item in list_serial_port_infos()]


def list_serial_port_labels() -> list[str]:
    return [item.label for item in list_serial_port_infos()]


def device_from_port_choice(choice: str) -> str:
    """Из строки 'COM10 — USB-SERIAL CH340' вернуть 'COM10'."""
    text = choice.strip()
    if " — " in text:
        return text.split(" — ", 1)[0].strip()
    return text


def guess_arduino_port(infos: list[SerialPortInfo]) -> str | None:
    """Только USB-UART / Arduino; Bluetooth-COM не выбираем автоматически."""
    if not infos:
        return None
    for info in infos:
        desc = info.description.lower()
        if "bluetooth" in desc:
            continue
        blob = f"{desc} {info.hwid}".lower()
        if any(hint in blob for hint in ARDUINO_PORT_HINTS):
            return info.device
    return None


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
