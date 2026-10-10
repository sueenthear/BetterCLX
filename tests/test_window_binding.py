"""Tests for the single-HWND binding controller contract."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from better_clx.services.window_actions import WindowBindingController
from better_clx.ui.binding_page import BindingPage


class WindowBindingControllerTests(unittest.TestCase):
    def test_new_binding_replaces_previous_target(self) -> None:
        controller = WindowBindingController()
        with patch.object(controller, "is_window", return_value=True):
            self.assertTrue(controller.bind_window(0x1001))
            self.assertEqual(controller.bound_hwnd, 0x1001)
            self.assertTrue(controller.bind_window(0x2002))
            self.assertEqual(controller.bound_hwnd, 0x2002)

    def test_unbind_clears_only_target(self) -> None:
        controller = WindowBindingController()
        with patch.object(controller, "is_window", return_value=True):
            controller.bind_window(0x1001)
            controller.unbind()
        self.assertIsNone(controller.bound_hwnd)
        self.assertFalse(controller.is_fullscreen)

    def test_invalid_target_is_rejected(self) -> None:
        controller = WindowBindingController()
        with patch.object(controller, "is_window", return_value=False):
            self.assertFalse(controller.bind_window(0x1001))
        self.assertIsNone(controller.bound_hwnd)

    def test_single_click_focus_delay_is_longer_than_double_click_window(self) -> None:
        self.assertGreaterEqual(BindingPage.FOCUS_DELAY_MS, 350)


if __name__ == "__main__":
    unittest.main()
