#!/usr/bin/env bash
# Linux / macOS: uv → зависимости → GUI
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_DIR="$REPO_ROOT/python"

step() { echo ""; echo "==> $*"; }

ensure_uv() {
  if command -v uv >/dev/null 2>&1; then
    step "uv найден: $(command -v uv)"
    return
  fi
  step "uv не найден — установка..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # shellcheck disable=SC1091
  [ -f "$HOME/.local/bin/env" ] && . "$HOME/.local/bin/env"
  export PATH="$HOME/.local/bin:$PATH"
  command -v uv >/dev/null 2>&1 || {
    echo "Ошибка: uv не установился. См. https://docs.astral.sh/uv/" >&2
    exit 1
  }
}

echo "========================================"
echo "  Пульт CH1-CH8 · Arduino + ULN2803A"
echo "========================================"

ensure_uv
cd "$PYTHON_DIR"

step "uv sync --group modern"
uv sync --group modern

step "Запуск GUI"
echo "Прошивка: firmware/multi_channel_driver/"

if uv run python gui_modern.py; then
  exit 0
fi

echo "Запуск лёгкого GUI (tkinter)..."
uv run python gui_light.py
