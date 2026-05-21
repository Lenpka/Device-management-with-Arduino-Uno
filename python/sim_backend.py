"""Виртуальное устройство с тем же протоколом SET / FREQ / PWM / GET (для режима показа)."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from gui_common import UiWorker

from arduino_client import BOOT_DELAY_S, CHANNEL_COUNT, PWM_CHANNELS

__all__ = ["SimChannelController", "SimDevice"]


class SimDevice:
    def __init__(self) -> None:
        self._levels = [0] * CHANNEL_COUNT
        self._freq_hz = [0] * CHANNEL_COUNT
        self._pwm = [0] * CHANNEL_COUNT
        self._blink_phase = 0.0

    def tick(self, dt: float) -> bool:
        changed = False
        self._blink_phase += dt
        for i in range(CHANNEL_COUNT):
            hz = self._freq_hz[i]
            if hz <= 0:
                continue
            period = 1.0 / hz
            half = period / 2.0
            t = self._blink_phase % period
            new = 1 if t < half else 0
            if self._levels[i] != new:
                self._levels[i] = new
                changed = True
        return changed

    def _stat_line(self) -> str:
        return "STAT " + ",".join(str(v) for v in self._levels)

    def command(self, line: str) -> list[str]:
        parts = line.strip().upper().split()
        if not parts:
            return ["ERR syntax"]
        cmd = parts[0]

        if cmd == "GET":
            return [self._stat_line()]

        if cmd == "SET" and len(parts) == 3:
            ch, st = int(parts[1]), int(parts[2])
            if not 1 <= ch <= CHANNEL_COUNT or st not in (0, 1):
                return ["ERR SET"]
            i = ch - 1
            self._freq_hz[i] = 0
            self._pwm[i] = 0
            self._levels[i] = st
            return ["ACK SET", self._stat_line()]

        if cmd == "FREQ" and len(parts) == 3:
            ch, hz = int(parts[1]), int(parts[2])
            if not 1 <= ch <= CHANNEL_COUNT or not 0 <= hz <= 100:
                return ["ERR FREQ"]
            i = ch - 1
            self._pwm[i] = 0
            self._freq_hz[i] = hz
            if hz == 0:
                self._levels[i] = 0
            return ["ACK FREQ", self._stat_line()]

        if cmd == "PWM" and len(parts) == 3:
            ch, duty = int(parts[1]), int(parts[2])
            if ch not in PWM_CHANNELS or not 0 <= duty <= 255:
                return ["ERR PWM"]
            i = ch - 1
            self._freq_hz[i] = 0
            self._pwm[i] = duty
            self._levels[i] = 1 if duty > 0 else 0
            return ["ACK PWM", self._stat_line()]

        return ["ERR unknown"]

    @property
    def levels(self) -> list[int]:
        return list(self._levels)


class SimChannelController:
    def __init__(
        self,
        on_log: Callable[[str], None],
        on_stat: Callable[[list[int]], None],
        on_tx: Callable[[str], None],
        on_connected: Callable[[bool], None],
    ) -> None:
        self._on_log = on_log
        self._on_stat = on_stat
        self._on_tx = on_tx
        self._on_connected = on_connected
        self._dev: SimDevice | None = None

    @property
    def connected(self) -> bool:
        return self._dev is not None

    def connect(self, port: str, worker: "UiWorker") -> None:
        def task() -> None:
            self._on_log(f"Подключение к {port}…")
            time.sleep(min(BOOT_DELAY_S, 1.2))
            self._dev = SimDevice()
            worker.post(lambda: self._on_connected(True))
            worker.post(lambda: self._run_line_sync("GET"))

        worker.run_bg(task)

    def disconnect(self) -> None:
        self._dev = None
        self._on_connected(False)

    def tick(self, worker: "UiWorker") -> None:
        if self._dev and self._dev.tick(0.05):
            worker.post(lambda: self._on_stat(self._dev.levels))

    def _run_line(self, line: str, worker: "UiWorker") -> None:
        if not self.connected or self._dev is None:
            worker.post(lambda: self._on_log("Сначала подключитесь"))
            return

        def task() -> None:
            worker.post(lambda: self._on_tx(line))
            time.sleep(0.06)
            replies = self._dev.command(line)
            levels = self._dev.levels

            def ui() -> None:
                for reply in replies:
                    self._on_log(reply)
                self._on_stat(levels)

            worker.post(ui)

        worker.run_bg(task)

    def _run_line_sync(self, line: str) -> None:
        if not self.connected or self._dev is None:
            return
        self._on_tx(line)
        time.sleep(0.06)
        for reply in self._dev.command(line):
            self._on_log(reply)
        self._on_stat(self._dev.levels)

    def set_on(self, ch: int, worker: "UiWorker") -> None:
        self._run_line(f"SET {ch} 1", worker)

    def set_off(self, ch: int, worker: "UiWorker") -> None:
        self._run_line(f"SET {ch} 0", worker)

    def set_freq(self, ch: int, hz: int, worker: "UiWorker") -> None:
        self._run_line(f"FREQ {ch} {hz}", worker)

    def set_pwm(self, ch: int, duty: int, worker: "UiWorker") -> None:
        self._run_line(f"PWM {ch} {duty}", worker)

    def refresh_stat(self, worker: "UiWorker") -> None:
        self._run_line("GET", worker)

    def all_off(self, worker: "UiWorker") -> None:
        def task() -> None:
            for ch in range(1, CHANNEL_COUNT + 1):
                self._run_line_sync(f"SET {ch} 0")
                time.sleep(0.04)

        if self.connected:
            worker.run_bg(task)
