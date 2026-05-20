"""Общая логика для лёгкого и современного GUI."""

from __future__ import annotations

import queue
import threading
from typing import Callable

from arduino_client import (
    CHANNEL_COUNT,
    PWM_CHANNELS,
    ChannelController,
    SerialPortInfo,
    device_from_port_choice,
    guess_arduino_port,
    list_serial_port_infos,
)

__all__ = [
    "CHANNEL_COUNT",
    "PWM_CHANNELS",
    "ChannelController",
    "UiWorker",
    "PORT_SCAN_MS",
    "channel_labels",
    "format_stat",
    "refresh_port_list",
]

PORT_SCAN_MS = 2000


class UiWorker:
    """Фоновые задачи Serial + доставка обновлений в UI-поток."""

    def __init__(self) -> None:
        self._ui: queue.Queue[Callable[[], None]] = queue.Queue()

    def post(self, fn: Callable[[], None]) -> None:
        self._ui.put(fn)

    def pump(self) -> None:
        while True:
            try:
                fn = self._ui.get_nowait()
            except queue.Empty:
                break
            fn()

    def run_bg(self, fn: Callable[[], None]) -> None:
        threading.Thread(target=fn, daemon=True).start()


def channel_labels() -> list[str]:
    labels = []
    for ch in range(1, CHANNEL_COUNT + 1):
        tag = "PWM" if ch in PWM_CHANNELS else "SET/FREQ"
        labels.append(f"CH{ch} ({tag})")
    return labels


def format_stat(levels: list[int]) -> str:
    if len(levels) != CHANNEL_COUNT:
        return "STAT: нет данных"
    parts = [f"CH{i + 1}:{'ON' if v else 'off'}" for i, v in enumerate(levels)]
    return "  |  ".join(parts)


def _devices_signature(infos: list[SerialPortInfo]) -> tuple[str, ...]:
    return tuple(info.device for info in infos)


def refresh_port_list(
    current_choice: str,
    last_signature: tuple[str, ...] | None,
    *,
    only_available: bool = True,
    auto_pick: bool = False,
) -> tuple[list[SerialPortInfo], list[str], str, str | None, tuple[str, ...]]:
    """
    Обновить список портов.

    auto_pick=True только при первом запуске — иначе не менять выбор пользователя.
    """
    infos = list_serial_port_infos(only_available=only_available)
    labels = [info.label for info in infos]
    signature = _devices_signature(infos)

    if not labels:
        empty = "(порты не найдены — подключите Arduino)"
        log = "COM: нет доступных портов" if signature != last_signature else None
        return [], [empty], empty, log, signature

    current_choice = (current_choice or "").strip()
    current_device = device_from_port_choice(current_choice)

    # 1) Точное совпадение строки в списке — не трогаем выбор
    if current_choice and current_choice in labels:
        selected = current_choice
    elif current_device:
        selected = current_choice
        for info in infos:
            if info.device.upper() == current_device.upper():
                selected = info.label
                break
    else:
        selected = labels[0]

    # 2) Автовыбор Arduino только при первом открытии (не при каждом опросе)
    if auto_pick and not current_device:
        preferred = guess_arduino_port(infos)
        if preferred:
            for info in infos:
                if info.device == preferred:
                    selected = info.label
                    break

    log: str | None = None
    if signature != last_signature:
        if current_device and current_device.upper() not in {d.upper() for d in signature}:
            log = f"COM: {current_device} недоступен (кабель отключён?)"
        else:
            log = f"COM: доступно {len(labels)} порт(ов)"

    return infos, labels, selected, log, signature
