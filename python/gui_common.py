"""Общая логика для лёгкого и современного GUI."""

from __future__ import annotations

import queue
import threading
from typing import Callable

from arduino_client import CHANNEL_COUNT, PWM_CHANNELS, ChannelController, list_serial_ports

__all__ = [
    "CHANNEL_COUNT",
    "PWM_CHANNELS",
    "ChannelController",
    "UiWorker",
    "channel_labels",
    "format_stat",
    "list_serial_ports",
]


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
