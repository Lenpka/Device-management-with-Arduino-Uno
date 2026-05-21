"""Скрытый доступ к окну показа: Ctrl+Shift+U (без подсказок в интерфейсе)."""

from __future__ import annotations

from typing import Any

PRESENT_HOTKEY = "<Control-Shift-Key-u>"

_present: Any = None


def bind_present_hotkey(root) -> None:
    root.bind(PRESENT_HOTKEY, _on_hotkey, add="+")


def _on_hotkey(_event) -> str:
    open_present_window(_event.widget.winfo_toplevel())
    return "break"


def open_present_window(master) -> None:
    global _present
    try:
        if _present is not None and _present.root.winfo_exists():
            _present.root.lift()
            _present.root.focus_force()
            return
    except Exception:
        _present = None

    from gui_present import PresentWindow

    _present = PresentWindow(master)


def clear_present_instance(win) -> None:
    global _present
    if _present is not None and getattr(_present, "root", None) == win:
        _present = None
