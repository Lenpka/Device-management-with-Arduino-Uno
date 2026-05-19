#!/usr/bin/env python3
"""
Лёгкий GUI: только стандартная библиотека tkinter + pyserial.
Минимальная нагрузка на ПК, полный функционал SET / FREQ / PWM / GET.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from arduino_client import CHANNEL_COUNT, PWM_CHANNELS
from gui_common import ChannelController, UiWorker, format_stat, list_serial_ports

POLL_MS = 500


class LightGuiApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("CH1–CH8 — лёгкий пульт (tkinter)")
        self.root.minsize(720, 520)

        self.worker = UiWorker()
        self.ctrl = ChannelController(self._log, self._on_stat, self._set_connected)
        self._poll_job: str | None = None
        self._stat_labels: list[tk.Label] = []
        self._freq_vars: list[tk.StringVar] = []
        self._pwm_vars: list[tk.IntVar] = []

        self._build()
        self._pump()

    def _build(self) -> None:
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill=tk.X)

        ttk.Label(top, text="COM:").pack(side=tk.LEFT)
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(top, textvariable=self.port_var, width=14)
        self.port_combo.pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Обновить", command=self._refresh_ports).pack(side=tk.LEFT)
        self.btn_connect = ttk.Button(top, text="Подключить", command=self._toggle_connect)
        self.btn_connect.pack(side=tk.LEFT, padx=8)
        ttk.Button(top, text="Все OFF", command=self._all_off).pack(side=tk.LEFT)
        self.poll_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            top, text="Опрос STAT", variable=self.poll_var, command=self._toggle_poll
        ).pack(side=tk.LEFT, padx=8)
        ttk.Button(top, text="GET", command=self._get_stat).pack(side=tk.LEFT)

        stat_row = ttk.Frame(self.root, padding=(8, 0))
        stat_row.pack(fill=tk.X)
        ttk.Label(stat_row, text="Логика на пинах:").pack(side=tk.LEFT)
        for ch in range(1, CHANNEL_COUNT + 1):
            lb = tk.Label(
                stat_row,
                text=f"CH{ch}:—",
                width=8,
                relief=tk.GROOVE,
                bg="#e8e8e8",
            )
            lb.pack(side=tk.LEFT, padx=2, pady=4)
            self._stat_labels.append(lb)

        grid = ttk.Frame(self.root, padding=8)
        grid.pack(fill=tk.BOTH, expand=True)
        for col in range(4):
            grid.columnconfigure(col, weight=1)

        for idx, ch in enumerate(range(1, CHANNEL_COUNT + 1)):
            row, col = divmod(idx, 4)
            self._add_channel(grid, ch, row, col)

        log_frame = ttk.LabelFrame(self.root, text="Журнал ACK / ERR / STAT", padding=4)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.log_box = scrolledtext.ScrolledText(log_frame, height=8, state=tk.DISABLED)
        self.log_box.pack(fill=tk.BOTH, expand=True)

        self.status_var = tk.StringVar(value="Не подключено")
        ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN).pack(
            fill=tk.X, padx=8, pady=(0, 8)
        )

        self._refresh_ports()

    def _add_channel(self, parent: ttk.Frame, ch: int, row: int, col: int) -> None:
        pwm = ch in PWM_CHANNELS
        lf = ttk.LabelFrame(parent, text=f"CH{ch}" + ("  PWM" if pwm else ""), padding=6)
        lf.grid(row=row, column=col, sticky="nsew", padx=4, pady=4)

        btn_row = ttk.Frame(lf)
        btn_row.pack(fill=tk.X)
        ttk.Button(btn_row, text="ON", width=6, command=lambda c=ch: self.ctrl.set_on(c, self.worker)).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(btn_row, text="OFF", width=6, command=lambda c=ch: self.ctrl.set_off(c, self.worker)).pack(
            side=tk.LEFT, padx=2
        )

        freq_var = tk.StringVar(value="2")
        self._freq_vars.append(freq_var)
        fr = ttk.Frame(lf)
        fr.pack(fill=tk.X, pady=4)
        ttk.Label(fr, text="FREQ Гц:").pack(side=tk.LEFT)
        ttk.Entry(fr, textvariable=freq_var, width=5).pack(side=tk.LEFT, padx=2)
        ttk.Button(
            fr,
            text="→",
            width=3,
            command=lambda c=ch, v=freq_var: self._apply_freq(c, v),
        ).pack(side=tk.LEFT)

        pwm_var = tk.IntVar(value=0)
        self._pwm_vars.append(pwm_var)
        pr = ttk.Frame(lf)
        pr.pack(fill=tk.X)
        scale = ttk.Scale(
            pr,
            from_=0,
            to=255,
            orient=tk.HORIZONTAL,
            variable=pwm_var,
            command=lambda _v, c=ch, pv=pwm_var: None,
        )
        scale.pack(fill=tk.X)
        if not pwm:
            scale.state(["disabled"])
        ttk.Button(
            pr,
            text="PWM",
            command=lambda c=ch, pv=pwm_var: self._apply_pwm(c, pv),
            state=tk.NORMAL if pwm else tk.DISABLED,
        ).pack(pady=2)

    def _apply_freq(self, ch: int, var: tk.StringVar) -> None:
        try:
            hz = int(var.get())
            if not 0 <= hz <= 100:
                raise ValueError
        except ValueError:
            messagebox.showwarning("FREQ", "Частота 0…100 Гц")
            return
        self.ctrl.set_freq(ch, hz, self.worker)

    def _apply_pwm(self, ch: int, var: tk.IntVar) -> None:
        self.ctrl.set_pwm(ch, int(var.get()), self.worker)

    def _refresh_ports(self) -> None:
        ports = list_serial_ports()
        self.port_combo["values"] = ports
        if ports and not self.port_var.get():
            self.port_var.set(ports[0])

    def _toggle_connect(self) -> None:
        if self.ctrl.connected:
            self.ctrl.disconnect()
            return
        port = self.port_var.get().strip()
        if not port:
            messagebox.showwarning("Порт", "Выберите COM-порт")
            return
        self.ctrl.connect(port, self.worker)

    def _set_connected(self, ok: bool) -> None:
        self.btn_connect.config(text="Отключить" if ok else "Подключить")
        self.status_var.set(f"Подключено: {self.port_var.get()}" if ok else "Не подключено")
        if not ok:
            self.poll_var.set(False)
            self._stop_poll()

    def _all_off(self) -> None:
        self.ctrl.all_off(self.worker)

    def _get_stat(self) -> None:
        self.ctrl.refresh_stat(self.worker)

    def _toggle_poll(self) -> None:
        if self.poll_var.get():
            if not self.ctrl.connected:
                self.poll_var.set(False)
                messagebox.showwarning("STAT", "Сначала подключитесь")
                return
            self._schedule_poll()
        else:
            self._stop_poll()

    def _schedule_poll(self) -> None:
        self._stop_poll()
        if self.poll_var.get() and self.ctrl.connected:
            self.ctrl.refresh_stat(self.worker)
            self._poll_job = self.root.after(POLL_MS, self._schedule_poll)

    def _stop_poll(self) -> None:
        if self._poll_job:
            self.root.after_cancel(self._poll_job)
            self._poll_job = None

    def _log(self, text: str) -> None:
        self.log_box.config(state=tk.NORMAL)
        self.log_box.insert(tk.END, text + "\n")
        self.log_box.see(tk.END)
        self.log_box.config(state=tk.DISABLED)

    def _on_stat(self, levels: list[int]) -> None:
        for i, v in enumerate(levels):
            color = "#9fdf9f" if v else "#e8e8e8"
            self._stat_labels[i].config(text=f"CH{i + 1}:{'1' if v else '0'}", bg=color)
        self.status_var.set(format_stat(levels))

    def _pump(self) -> None:
        self.worker.pump()
        self.root.after(40, self._pump)

    def run(self) -> None:
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()

    def _on_close(self) -> None:
        self._stop_poll()
        self.ctrl.disconnect()
        self.root.destroy()


def main() -> None:
    LightGuiApp().run()


if __name__ == "__main__":
    main()
