#!/usr/bin/env python3
"""
Окно мониторинга протокола (отдельный интерфейс).
Открывается из основного пульта: Ctrl+Shift+U.
"""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk
from tkinter import messagebox

try:
    import customtkinter as ctk
except ImportError:
    raise SystemExit("Нужен customtkinter (как для gui_modern.py)") from None

from arduino_client import CHANNEL_COUNT, PWM_CHANNELS, device_from_port_choice
from gui_common import UiWorker, format_stat
from present_access import clear_present_instance
from sim_backend import SimChannelController

POLL_MS = 500
PRESENT_PORT = "COM10 — USB-SERIAL CH340 (wch.cn)"

STACK_TEXT = (
    "Python (верхний уровень)\n"
    "    │  115200 8N1, кадр ASCII + \\n\n"
    "    ▼\n"
    "Arduino UNO\n"
    "    │  SET · FREQ · PWM · GET\n"
    "    ▼\n"
    "ULN2803A  →  CH1 … CH8"
)

BG = "#141820"
PANEL = "#1e2430"
ACCENT = "#2dd4bf"
ACCENT_DIM = "#115e59"
ON_BADGE = "#14532d"
OFF_BADGE = "#27272a"
TX_COLOR = "#7dd3fc"
RX_COLOR = "#86efac"


class PresentWindow:
    def __init__(self, master: tk.Misc) -> None:
        self.root = ctk.CTkToplevel(master)
        self.root.title("Монитор протокола · CH1–CH8")
        self.root.geometry("1040x700")
        self.root.minsize(920, 620)
        self.root.configure(fg_color=BG)

        self.worker = UiWorker()
        self.ctrl = SimChannelController(
            self._log,
            self._on_stat,
            self._show_tx,
            self._set_connected,
        )
        self._poll_job: str | None = None
        self._connecting = False
        self._scenario = False
        self._stat_badges: list[ctk.CTkLabel] = []
        self._freq_entries: list[ctk.CTkEntry] = []
        self._pwm_sliders: list[ctk.CTkSlider] = []
        self._stat_cache = [-1] * CHANNEL_COUNT

        self._build()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        bind_present_hotkey_local(self.root)
        self._pump()

    def _build(self) -> None:
        header = ctk.CTkFrame(self.root, fg_color=PANEL, corner_radius=14)
        header.pack(fill=tk.X, padx=14, pady=(14, 6))

        ctk.CTkLabel(
            header,
            text="Монитор обмена",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=ACCENT,
        ).pack(side=tk.LEFT, padx=16, pady=14)

        self.port_var = tk.StringVar(value=PRESENT_PORT)
        ctk.CTkComboBox(
            header,
            variable=self.port_var,
            values=[PRESENT_PORT],
            width=320,
            state="readonly",
            dropdown_font=ctk.CTkFont(size=12),
        ).pack(side=tk.RIGHT, padx=6, pady=12)
        ctk.CTkLabel(header, text="COM:", text_color="gray65").pack(side=tk.RIGHT)

        self.btn_connect = ctk.CTkButton(
            header,
            text="Подключить",
            width=120,
            fg_color=ACCENT_DIM,
            hover_color=ACCENT,
            command=self._toggle_connect,
        )
        self.btn_connect.pack(side=tk.RIGHT, padx=10, pady=12)

        toolbar = ctk.CTkFrame(self.root, fg_color=BG)
        toolbar.pack(fill=tk.X, padx=14, pady=4)
        ctk.CTkButton(
            toolbar,
            text="Все OFF",
            fg_color="#7f1d1d",
            hover_color="#991b1b",
            command=lambda: self.ctrl.all_off(self.worker),
        ).pack(side=tk.LEFT, padx=4)
        ctk.CTkButton(toolbar, text="GET", command=lambda: self.ctrl.refresh_stat(self.worker)).pack(
            side=tk.LEFT, padx=4
        )
        self.poll_switch = ctk.CTkSwitch(
            toolbar, text="Автоопрос STAT", command=self._toggle_poll
        )
        self.poll_switch.pack(side=tk.LEFT, padx=16)
        ctk.CTkButton(
            toolbar,
            text="Последовательность",
            fg_color=PANEL,
            border_width=1,
            border_color=ACCENT_DIM,
            command=self._run_sequence,
        ).pack(side=tk.RIGHT, padx=4)

        body = ctk.CTkFrame(self.root, fg_color=BG)
        body.pack(fill=tk.BOTH, expand=True, padx=14, pady=6)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        side = ctk.CTkFrame(body, fg_color=PANEL, corner_radius=12, width=300)
        side.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        side.grid_propagate(False)

        ctk.CTkLabel(
            side,
            text="Стек управления",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
        ).pack(fill=tk.X, padx=12, pady=(12, 6))
        ctk.CTkLabel(
            side,
            text=STACK_TEXT,
            font=ctk.CTkFont(family="Consolas", size=12),
            justify=tk.LEFT,
            anchor="nw",
            text_color="gray80",
        ).pack(fill=tk.BOTH, expand=True, padx=12, pady=4)

        ctk.CTkLabel(side, text="Передача (хост → UNO)", text_color="gray60", anchor="w").pack(
            fill=tk.X, padx=12, pady=(8, 0)
        )
        self.tx_label = ctk.CTkLabel(
            side,
            text="—",
            font=ctk.CTkFont(family="Consolas", size=13),
            text_color=TX_COLOR,
            anchor="w",
            wraplength=260,
        )
        self.tx_label.pack(fill=tk.X, padx=12, pady=2)

        ctk.CTkLabel(side, text="Приём (UNO → хост)", text_color="gray60", anchor="w").pack(
            fill=tk.X, padx=12, pady=(10, 0)
        )
        self.rx_label = ctk.CTkLabel(
            side,
            text="—",
            font=ctk.CTkFont(family="Consolas", size=13),
            text_color=RX_COLOR,
            anchor="w",
            wraplength=260,
        )
        self.rx_label.pack(fill=tk.X, padx=12, pady=(2, 12))

        main = ctk.CTkFrame(body, fg_color=BG)
        main.grid(row=0, column=1, sticky="nsew")
        main.rowconfigure(1, weight=1)
        main.columnconfigure(0, weight=1)

        badges_row = ctk.CTkFrame(main, fg_color=PANEL, corner_radius=10)
        badges_row.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ctk.CTkLabel(
            badges_row,
            text="STAT — логика на выходах Arduino",
            text_color="gray65",
            font=ctk.CTkFont(size=11),
        ).pack(anchor="w", padx=12, pady=(8, 4))
        br = ctk.CTkFrame(badges_row, fg_color=PANEL)
        br.pack(fill=tk.X, padx=8, pady=(0, 10))
        for ch in range(1, CHANNEL_COUNT + 1):
            b = ctk.CTkLabel(
                br,
                text=f"CH{ch}",
                width=76,
                height=30,
                corner_radius=8,
                fg_color=OFF_BADGE,
            )
            b.pack(side=tk.LEFT, padx=3)
            self._stat_badges.append(b)

        grid_wrap = ctk.CTkScrollableFrame(main, fg_color=PANEL, corner_radius=10)
        grid_wrap.grid(row=1, column=0, sticky="nsew")
        for col in range(4):
            grid_wrap.grid_columnconfigure(col, weight=1)
        for idx, ch in enumerate(range(1, CHANNEL_COUNT + 1)):
            row, col = divmod(idx, 4)
            self._add_channel_card(grid_wrap, ch, row, col)

        log_frame = ctk.CTkFrame(self.root, fg_color=PANEL, corner_radius=10)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 6))
        ctk.CTkLabel(
            log_frame,
            text="Журнал Serial",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        ).pack(anchor="w", padx=12, pady=(8, 4))
        self.log_box = ctk.CTkTextbox(
            log_frame,
            height=140,
            font=ctk.CTkFont(family="Consolas", size=12),
            fg_color="#0c0f14",
            activate_scrollbars=True,
        )
        self.log_box.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.status_label = ctk.CTkLabel(
            self.root,
            text="Не подключено",
            height=28,
            fg_color="#0c0f14",
            corner_radius=0,
            anchor="w",
        )
        self.status_label.pack(fill=tk.X, padx=0, pady=(0, 10))

    def _add_channel_card(
        self, parent: ctk.CTkScrollableFrame, ch: int, row: int, col: int
    ) -> None:
        pwm = ch in PWM_CHANNELS
        card = ctk.CTkFrame(parent, fg_color="#252b38", corner_radius=10, border_width=1, border_color="#333")
        card.grid(row=row, column=col, sticky="nsew", padx=6, pady=6)

        title = f"CH{ch}" + (" · PWM" if pwm else "")
        ctk.CTkLabel(card, text=title, font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(8, 4))

        row_btns = ctk.CTkFrame(card, fg_color="transparent")
        row_btns.pack(fill=tk.X, padx=8)
        ctk.CTkButton(
            row_btns,
            text="ON",
            width=56,
            height=28,
            fg_color=ACCENT_DIM,
            hover_color=ACCENT,
            command=lambda c=ch: self.ctrl.set_on(c, self.worker),
        ).pack(side=tk.LEFT, padx=2)
        ctk.CTkButton(
            row_btns,
            text="OFF",
            width=56,
            height=28,
            command=lambda c=ch: self.ctrl.set_off(c, self.worker),
        ).pack(side=tk.LEFT, padx=2)

        fr = ctk.CTkFrame(card, fg_color="transparent")
        fr.pack(fill=tk.X, padx=8, pady=6)
        ctk.CTkLabel(fr, text="FREQ Гц", width=56, anchor="w").pack(side=tk.LEFT)
        ent = ctk.CTkEntry(fr, width=48)
        ent.insert(0, "5")
        ent.pack(side=tk.LEFT, padx=4)
        self._freq_entries.append(ent)
        ctk.CTkButton(
            fr,
            text="→",
            width=36,
            command=lambda c=ch, e=ent: self._apply_freq(c, e),
        ).pack(side=tk.LEFT)

        pr = ctk.CTkFrame(card, fg_color="transparent")
        pr.pack(fill=tk.X, padx=8, pady=(0, 10))
        sl = ctk.CTkSlider(pr, from_=0, to=255, number_of_steps=255)
        sl.set(128)
        sl.pack(fill=tk.X, pady=4)
        if not pwm:
            sl.configure(state=tk.DISABLED)
        self._pwm_sliders.append(sl)
        ctk.CTkButton(
            pr,
            text="PWM",
            height=26,
            state=tk.NORMAL if pwm else tk.DISABLED,
            command=lambda c=ch, s=sl: self.ctrl.set_pwm(c, int(s.get()), self.worker),
        ).pack()

    def _apply_freq(self, ch: int, entry: ctk.CTkEntry) -> None:
        try:
            hz = int(entry.get())
            if not 0 <= hz <= 100:
                raise ValueError
        except ValueError:
            messagebox.showwarning("FREQ", "Частота 0…100 Гц", parent=self.root)
            return
        self.ctrl.set_freq(ch, hz, self.worker)

    def _toggle_connect(self) -> None:
        if self.ctrl.connected:
            self.ctrl.disconnect()
            return
        port = device_from_port_choice(self.port_var.get()) or "COM10"
        self._connecting = True
        self.btn_connect.configure(state=tk.DISABLED)
        self.ctrl.connect(port, self.worker)

    def _set_connected(self, ok: bool) -> None:
        self._connecting = False
        self.btn_connect.configure(state=tk.NORMAL, text="Отключить" if ok else "Подключить")
        dev = device_from_port_choice(self.port_var.get()) or "COM10"
        if ok:
            self.status_label.configure(text=f"Подключено: {dev}")
            self._log("Связь установлена")
        else:
            self.poll_switch.deselect()
            self._stop_poll()
            self.status_label.configure(text="Не подключено")
            self.tx_label.configure(text="—")
            self.rx_label.configure(text="—")

    def _show_tx(self, line: str) -> None:
        self.tx_label.configure(text=line)

    def _log(self, text: str) -> None:
        self.log_box.insert(tk.END, text + "\n")
        self.log_box.see(tk.END)
        if text.startswith(("ACK", "ERR", "STAT")):
            self.rx_label.configure(text=text)

    def _on_stat(self, levels: list[int]) -> None:
        for i, v in enumerate(levels):
            if self._stat_cache[i] == v:
                continue
            self._stat_cache[i] = v
            self._stat_badges[i].configure(
                text=f"CH{i + 1}  {'1' if v else '0'}",
                fg_color=ON_BADGE if v else OFF_BADGE,
            )
        self.status_label.configure(text=format_stat(levels))

    def _toggle_poll(self) -> None:
        if self.poll_switch.get():
            if not self.ctrl.connected:
                self.poll_switch.deselect()
                messagebox.showwarning("STAT", "Сначала подключитесь", parent=self.root)
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

    def _run_sequence(self) -> None:
        if self._scenario or not self.ctrl.connected:
            if not self.ctrl.connected:
                messagebox.showwarning("Последовательность", "Сначала подключитесь", parent=self.root)
            return
        self._scenario = True
        self._log("— последовательность SET → FREQ → PWM → GET —")
        steps = [
            (0.0, lambda: self.ctrl.set_on(1, self.worker)),
            (1.2, lambda: self.ctrl.set_freq(1, 8, self.worker)),
            (4.0, lambda: self.ctrl.set_pwm(5, 200, self.worker)),
            (6.5, lambda: self.ctrl.set_pwm(5, 64, self.worker)),
            (8.0, lambda: self.ctrl.set_off(1, self.worker)),
            (8.4, lambda: self.ctrl.refresh_stat(self.worker)),
            (10.0, lambda: self.ctrl.all_off(self.worker)),
            (10.3, self._sequence_done),
        ]
        t0 = time.monotonic()

        def tick() -> None:
            elapsed = time.monotonic() - t0
            while steps and steps[0][0] <= elapsed:
                _, fn = steps.pop(0)
                fn()
            if steps:
                self.root.after(80, tick)

        tick()

    def _sequence_done(self) -> None:
        self._scenario = False
        self._log("— готово —")

    def _pump(self) -> None:
        self.worker.pump()
        self.ctrl.tick(self.worker)
        self.root.after(50, self._pump)

    def _on_close(self) -> None:
        self._stop_poll()
        self.ctrl.disconnect()
        clear_present_instance(self.root)
        self.root.destroy()


def bind_present_hotkey_local(root) -> None:
    """Повторное Ctrl+Shift+U внутри окна — поднять на передний план."""
    from present_access import PRESENT_HOTKEY, open_present_window

    def handler(event):
        open_present_window(event.widget.winfo_toplevel())
        return "break"

    root.bind(PRESENT_HOTKEY, handler, add="+")


def main() -> None:
    root = ctk.CTk()
    root.withdraw()
    PresentWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
