#!/usr/bin/env python3
"""
Современный GUI на CustomTkinter (pip install customtkinter).
Тот же функционал, что gui_light.py: SET / FREQ / PWM / GET, 8 каналов CH1–CH8.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk
from tkinter import messagebox

try:
    import customtkinter as ctk
except ImportError:
    raise SystemExit(
        "Установите: pip install customtkinter\n"
        "Лёгкая версия без доп. зависимостей: python gui_light.py"
    ) from None

from arduino_client import CHANNEL_COUNT, PWM_CHANNELS
from gui_common import ChannelController, UiWorker, format_stat, list_serial_ports

POLL_MS = 500

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class ModernGuiApp:
    def __init__(self) -> None:
        self.root = ctk.CTk()
        self.root.title("Управление CH1–CH8 · ULN2803A")
        self.root.geometry("960x640")
        self.root.minsize(860, 580)

        self.worker = UiWorker()
        self.ctrl = ChannelController(self._log, self._on_stat, self._set_connected)
        self._poll_job: str | None = None
        self._stat_badges: list[ctk.CTkLabel] = []
        self._freq_entries: list[ctk.CTkEntry] = []
        self._pwm_sliders: list[ctk.CTkSlider] = []

        self._build()
        self._pump()

    def _build(self) -> None:
        header = ctk.CTkFrame(self.root, corner_radius=12)
        header.pack(fill=tk.X, padx=16, pady=(16, 8))

        ctk.CTkLabel(
            header,
            text="Пульт выходных каналов",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(side=tk.LEFT, padx=12, pady=12)

        self.port_var = tk.StringVar()
        self.port_menu = ctk.CTkOptionMenu(header, variable=self.port_var, values=["—"])
        self.port_menu.pack(side=tk.RIGHT, padx=4, pady=12)

        ctk.CTkButton(header, text="↻", width=36, command=self._refresh_ports).pack(
            side=tk.RIGHT, padx=4, pady=12
        )
        self.btn_connect = ctk.CTkButton(
            header, text="Подключить", width=120, command=self._toggle_connect
        )
        self.btn_connect.pack(side=tk.RIGHT, padx=8, pady=12)

        toolbar = ctk.CTkFrame(self.root, fg_color="transparent")
        toolbar.pack(fill=tk.X, padx=16, pady=4)

        ctk.CTkButton(toolbar, text="Все OFF", fg_color="#8b3a3a", command=self._all_off).pack(
            side=tk.LEFT, padx=4
        )
        ctk.CTkButton(toolbar, text="GET / STAT", command=self._get_stat).pack(side=tk.LEFT, padx=4)
        self.poll_switch = ctk.CTkSwitch(
            toolbar, text="Автоопрос STAT", command=self._toggle_poll
        )
        self.poll_switch.pack(side=tk.LEFT, padx=16)

        stat_frame = ctk.CTkFrame(self.root, corner_radius=10)
        stat_frame.pack(fill=tk.X, padx=16, pady=8)
        ctk.CTkLabel(
            stat_frame,
            text="Логический уровень на пинах Arduino (не состояние нагрузки)",
            font=ctk.CTkFont(size=12),
            text_color="gray70",
        ).pack(anchor="w", padx=12, pady=(8, 4))

        badges = ctk.CTkFrame(stat_frame, fg_color="transparent")
        badges.pack(fill=tk.X, padx=8, pady=(0, 10))
        for ch in range(1, CHANNEL_COUNT + 1):
            b = ctk.CTkLabel(
                badges,
                text=f"CH{ch}",
                width=72,
                height=32,
                corner_radius=8,
                fg_color="#2b2b2b",
            )
            b.pack(side=tk.LEFT, padx=4)
            self._stat_badges.append(b)

        scroll = ctk.CTkScrollableFrame(self.root, label_text="Выходные каналы CH1 … CH8")
        scroll.pack(fill=tk.BOTH, expand=True, padx=16, pady=8)

        grid = ctk.CTkFrame(scroll, fg_color="transparent")
        grid.pack(fill=tk.BOTH, expand=True)
        for col in range(4):
            grid.grid_columnconfigure(col, weight=1)

        for idx, ch in enumerate(range(1, CHANNEL_COUNT + 1)):
            row, col = divmod(idx, 4)
            self._add_channel_card(grid, ch, row, col)

        log_frame = ctk.CTkFrame(self.root, corner_radius=10)
        log_frame.pack(fill=tk.BOTH, expand=False, padx=16, pady=(0, 8))
        ctk.CTkLabel(log_frame, text="Журнал", anchor="w").pack(fill=tk.X, padx=12, pady=(8, 0))
        self.log_box = ctk.CTkTextbox(log_frame, height=100, font=ctk.CTkFont(family="Consolas", size=12))
        self.log_box.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)
        self.log_box.configure(state=tk.DISABLED)

        self.status_label = ctk.CTkLabel(
            self.root, text="Не подключено", anchor="w", text_color="gray60"
        )
        self.status_label.pack(fill=tk.X, padx=20, pady=(0, 12))

        self._refresh_ports()

    def _add_channel_card(self, parent: ctk.CTkFrame, ch: int, row: int, col: int) -> None:
        pwm = ch in PWM_CHANNELS
        card = ctk.CTkFrame(parent, corner_radius=12, border_width=1, border_color="#3a3a4a")
        card.grid(row=row, column=col, sticky="nsew", padx=6, pady=6)

        title = f"CH{ch}"
        if pwm:
            title += "  ·  PWM"
        ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=15, weight="bold")).pack(
            anchor="w", padx=12, pady=(10, 6)
        )

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill=tk.X, padx=10)
        ctk.CTkButton(
            btn_row,
            text="ON",
            width=70,
            fg_color="#1f6aa5",
            command=lambda c=ch: self.ctrl.set_on(c, self.worker),
        ).pack(side=tk.LEFT, padx=4)
        ctk.CTkButton(
            btn_row,
            text="OFF",
            width=70,
            fg_color="#444",
            command=lambda c=ch: self.ctrl.set_off(c, self.worker),
        ).pack(side=tk.LEFT, padx=4)

        ctk.CTkLabel(card, text="FREQ (меандр, Гц 0–100)", anchor="w", text_color="gray65").pack(
            anchor="w", padx=12, pady=(8, 0)
        )
        freq_row = ctk.CTkFrame(card, fg_color="transparent")
        freq_row.pack(fill=tk.X, padx=10, pady=4)
        freq_entry = ctk.CTkEntry(freq_row, width=60, placeholder_text="Гц")
        freq_entry.insert(0, "2")
        freq_entry.pack(side=tk.LEFT)
        self._freq_entries.append(freq_entry)
        ctk.CTkButton(
            freq_row,
            text="Применить",
            width=90,
            command=lambda c=ch, e=freq_entry: self._apply_freq(c, e),
        ).pack(side=tk.LEFT, padx=8)

        ctk.CTkLabel(card, text="PWM (analogWrite)", anchor="w", text_color="gray65").pack(
            anchor="w", padx=12, pady=(6, 0)
        )
        slider = ctk.CTkSlider(card, from_=0, to=255, number_of_steps=255)
        slider.set(0)
        slider.pack(fill=tk.X, padx=12, pady=6)
        if not pwm:
            slider.configure(state=tk.DISABLED)
        self._pwm_sliders.append(slider)

        duty_label = ctk.CTkLabel(card, text="duty: 0", text_color="gray60")
        duty_label.pack(anchor="w", padx=12)

        def on_slide(v: float, lbl=duty_label) -> None:
            lbl.configure(text=f"duty: {int(v)}")

        slider.configure(command=on_slide)

        btn_pwm = ctk.CTkButton(
            card,
            text="Применить PWM",
            command=lambda c=ch, s=slider: self._apply_pwm(c, s),
        )
        btn_pwm.pack(pady=(0, 12))
        if not pwm:
            btn_pwm.configure(state=tk.DISABLED)

    def _apply_freq(self, ch: int, entry: ctk.CTkEntry) -> None:
        try:
            hz = int(entry.get().strip())
            if not 0 <= hz <= 100:
                raise ValueError
        except ValueError:
            messagebox.showwarning("FREQ", "Частота 0…100 Гц")
            return
        self.ctrl.set_freq(ch, hz, self.worker)

    def _apply_pwm(self, ch: int, slider: ctk.CTkSlider) -> None:
        self.ctrl.set_pwm(ch, int(slider.get()), self.worker)

    def _refresh_ports(self) -> None:
        ports = list_serial_ports() or ["—"]
        self.port_menu.configure(values=ports)
        if ports[0] != "—":
            self.port_var.set(ports[0])

    def _toggle_connect(self) -> None:
        if self.ctrl.connected:
            self.ctrl.disconnect()
            return
        port = self.port_var.get().strip()
        if not port or port == "—":
            messagebox.showwarning("Порт", "Выберите COM-порт")
            return
        self.ctrl.connect(port, self.worker)

    def _set_connected(self, ok: bool) -> None:
        self.btn_connect.configure(text="Отключить" if ok else "Подключить")
        if ok:
            self.status_label.configure(text=f"Подключено · {self.port_var.get()}")
        else:
            self.status_label.configure(text="Не подключено")
            self.poll_switch.deselect()
            self._stop_poll()

    def _all_off(self) -> None:
        self.ctrl.all_off(self.worker)

    def _get_stat(self) -> None:
        self.ctrl.refresh_stat(self.worker)

    def _toggle_poll(self) -> None:
        if self.poll_switch.get():
            if not self.ctrl.connected:
                self.poll_switch.deselect()
                messagebox.showwarning("STAT", "Сначала подключитесь")
                return
            self._schedule_poll()
        else:
            self._stop_poll()

    def _schedule_poll(self) -> None:
        self._stop_poll()
        if self.poll_switch.get() and self.ctrl.connected:
            self.ctrl.refresh_stat(self.worker)
            self._poll_job = self.root.after(POLL_MS, self._schedule_poll)

    def _stop_poll(self) -> None:
        if self._poll_job:
            self.root.after_cancel(self._poll_job)
            self._poll_job = None

    def _log(self, text: str) -> None:
        self.log_box.configure(state=tk.NORMAL)
        self.log_box.insert(tk.END, text + "\n")
        self.log_box.see(tk.END)
        self.log_box.configure(state=tk.DISABLED)

    def _on_stat(self, levels: list[int]) -> None:
        on_color = "#1a5c38"
        off_color = "#2b2b2b"
        for i, v in enumerate(levels):
            self._stat_badges[i].configure(
                text=f"CH{i + 1}  {'ON' if v else 'off'}",
                fg_color=on_color if v else off_color,
            )
        self.status_label.configure(text=format_stat(levels))

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
    ModernGuiApp().run()


if __name__ == "__main__":
    main()
