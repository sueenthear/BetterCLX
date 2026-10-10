"""Win32 input polling and PostMessage output scoped to one HWND."""

from __future__ import annotations

import string
from collections.abc import Iterable

import win32api
import win32con
import win32gui


VK_CODES: dict[str, int] = {
    "BACKSPACE": win32con.VK_BACK,
    "TAB": win32con.VK_TAB,
    "ENTER": win32con.VK_RETURN,
    "SHIFT": win32con.VK_SHIFT,
    "CTRL": win32con.VK_CONTROL,
    "ALT": win32con.VK_MENU,
    "PAUSE": win32con.VK_PAUSE,
    "CAPSLOCK": win32con.VK_CAPITAL,
    "ESC": win32con.VK_ESCAPE,
    "SPACE": win32con.VK_SPACE,
    "PAGEUP": win32con.VK_PRIOR,
    "PAGEDOWN": win32con.VK_NEXT,
    "END": win32con.VK_END,
    "HOME": win32con.VK_HOME,
    "LEFT": win32con.VK_LEFT,
    "UP": win32con.VK_UP,
    "RIGHT": win32con.VK_RIGHT,
    "DOWN": win32con.VK_DOWN,
    "INSERT": win32con.VK_INSERT,
    "DELETE": win32con.VK_DELETE,
    "WIN": win32con.VK_LWIN,
    "NUMLOCK": win32con.VK_NUMLOCK,
    "SCROLLLOCK": win32con.VK_SCROLL,
    "PRINTSCREEN": win32con.VK_SNAPSHOT,
    "APPS": win32con.VK_APPS,
    "鼠标左键": win32con.VK_LBUTTON,
    "鼠标右键": win32con.VK_RBUTTON,
    "鼠标中键": win32con.VK_MBUTTON,
    ";": 0xBA,
    "=": 0xBB,
    ",": 0xBC,
    "-": 0xBD,
    ".": 0xBE,
    "/": 0xBF,
    "`": 0xC0,
    "[": 0xDB,
    "\\": 0xDC,
    "]": 0xDD,
    "'": 0xDE,
}
for _letter in string.ascii_uppercase:
    VK_CODES[_letter] = ord(_letter)
for _digit in string.digits:
    VK_CODES[_digit] = ord(_digit)
for _index in range(1, 25):
    VK_CODES[f"F{_index}"] = getattr(win32con, f"VK_F{_index}")

_KEY_ALIASES = {
    "CONTROL": "CTRL",
    "RETURN": "ENTER",
    "ESCAPE": "ESC",
    "SPACEBAR": "SPACE",
    "PGUP": "PAGEUP",
    "PGDN": "PAGEDOWN",
    "DEL": "DELETE",
    "INS": "INSERT",
    "LCTRL": "CTRL",
    "RCTRL": "CTRL",
    "LSHIFT": "SHIFT",
    "RSHIFT": "SHIFT",
    "LALT": "ALT",
    "RALT": "ALT",
}

_EXTENDED_KEYS = {
    win32con.VK_RMENU,
    win32con.VK_RCONTROL,
    win32con.VK_INSERT,
    win32con.VK_DELETE,
    win32con.VK_HOME,
    win32con.VK_END,
    win32con.VK_PRIOR,
    win32con.VK_NEXT,
    win32con.VK_LEFT,
    win32con.VK_RIGHT,
    win32con.VK_UP,
    win32con.VK_DOWN,
    win32con.VK_NUMLOCK,
    win32con.VK_SNAPSHOT,
    win32con.VK_LWIN,
    win32con.VK_RWIN,
    win32con.VK_APPS,
}


def normalize_key_name(name: str) -> str:
    normalized = name.strip().upper().replace(" ", "")
    return _KEY_ALIASES.get(normalized, normalized)


def key_to_vk(name: str) -> int | None:
    return VK_CODES.get(normalize_key_name(name))


def qt_key_name(key: int, text: str = "") -> str:
    """Convert a Qt key event to a stable Win32-friendly key name."""
    from PySide6.QtCore import Qt

    qt_key = Qt.Key(key)
    special = {
        Qt.Key.Key_Backspace: "BACKSPACE",
        Qt.Key.Key_Tab: "TAB",
        Qt.Key.Key_Return: "ENTER",
        Qt.Key.Key_Enter: "ENTER",
        Qt.Key.Key_Shift: "SHIFT",
        Qt.Key.Key_Control: "CTRL",
        Qt.Key.Key_Alt: "ALT",
        Qt.Key.Key_Pause: "PAUSE",
        Qt.Key.Key_CapsLock: "CAPSLOCK",
        Qt.Key.Key_Escape: "ESC",
        Qt.Key.Key_Space: "SPACE",
        Qt.Key.Key_PageUp: "PAGEUP",
        Qt.Key.Key_PageDown: "PAGEDOWN",
        Qt.Key.Key_End: "END",
        Qt.Key.Key_Home: "HOME",
        Qt.Key.Key_Left: "LEFT",
        Qt.Key.Key_Up: "UP",
        Qt.Key.Key_Right: "RIGHT",
        Qt.Key.Key_Down: "DOWN",
        Qt.Key.Key_Insert: "INSERT",
        Qt.Key.Key_Delete: "DELETE",
        Qt.Key.Key_Meta: "WIN",
        Qt.Key.Key_Semicolon: ";",
        Qt.Key.Key_Equal: "=",
        Qt.Key.Key_Comma: ",",
        Qt.Key.Key_Minus: "-",
        Qt.Key.Key_Period: ".",
        Qt.Key.Key_Slash: "/",
        Qt.Key.Key_QuoteLeft: "`",
        Qt.Key.Key_BracketLeft: "[",
        Qt.Key.Key_Backslash: "\\",
        Qt.Key.Key_BracketRight: "]",
        Qt.Key.Key_Apostrophe: "'",
    }
    if qt_key in special:
        return normalize_key_name(special[qt_key])
    if Qt.Key.Key_F1 <= qt_key <= Qt.Key.Key_F24:
        return f"F{int(qt_key) - int(Qt.Key.Key_F1) + 1}"
    if text and text.isprintable():
        return normalize_key_name(text[0])
    return normalize_key_name(qt_key.name.removeprefix("Key_"))


def _key_lparam(vk: int, released: bool = False) -> int:
    scan_code = win32api.MapVirtualKey(vk, 0) & 0xFF
    value = 1 | (scan_code << 16)
    if vk in _EXTENDED_KEYS:
        value |= 1 << 24
    if released:
        value |= (1 << 30) | (1 << 31)
    return value


def _signed_word(value: int) -> int:
    return value & 0xFFFF


def _mouse_lparam(x: int, y: int) -> int:
    return _signed_word(x) | (_signed_word(y) << 16)


class Win32Input:
    """Read global key state and send output messages to a specific HWND."""

    def __init__(self) -> None:
        self._held: dict[int, set[int]] = {}

    @staticmethod
    def is_window(hwnd: int | None) -> bool:
        return bool(hwnd and win32gui.IsWindow(hwnd))

    @staticmethod
    def is_key_down(key_name: str) -> bool:
        vk = key_to_vk(key_name)
        return bool(vk is not None and win32api.GetAsyncKeyState(vk) & 0x8000)

    def send_key(self, hwnd: int | None, key_name: str, action: str) -> bool:
        vk = key_to_vk(key_name)
        if not self.is_window(hwnd) or vk is None:
            return False
        if action == "press":
            held = self._held.setdefault(int(hwnd), set())
            if vk not in held:
                win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, vk, _key_lparam(vk))
                held.add(vk)
        elif action == "release":
            win32api.PostMessage(hwnd, win32con.WM_KEYUP, vk, _key_lparam(vk, released=True))
            self._held.setdefault(int(hwnd), set()).discard(vk)
        else:
            return False
        return True

    def send_scroll(self, hwnd: int | None, direction: str) -> bool:
        if not self.is_window(hwnd):
            return False
        delta = 120 if direction == "up" else -120
        cursor_x, cursor_y = win32api.GetCursorPos()
        wparam = ((delta & 0xFFFF) << 16) | (win32api.GetKeyState(win32con.VK_SHIFT) & 1)
        win32api.PostMessage(
            hwnd,
            win32con.WM_MOUSEWHEEL,
            wparam,
            _mouse_lparam(cursor_x, cursor_y),
        )
        return True

    def release_all(self, hwnd: int | None) -> None:
        if not hwnd:
            return
        for vk in tuple(self._held.get(int(hwnd), set())):
            if self.is_window(hwnd):
                win32api.PostMessage(hwnd, win32con.WM_KEYUP, vk, _key_lparam(vk, released=True))
        self._held.pop(int(hwnd), None)

    def validate_keys(self, keys: Iterable[str]) -> list[str]:
        return [key for key in keys if key_to_vk(key) is not None]
