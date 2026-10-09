"""Opens the real window with a fake phone. Skipped where there is no screen or tkinter."""

import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import tkinter as tk

    _root = tk.Tk()
    _root.destroy()
    HAVE_SCREEN = True
except Exception:  # noqa: BLE001 - no tkinter or no display
    HAVE_SCREEN = False


class FakePhone:
    def __init__(self):
        self.locked = False
        self.hidden = {"com.android.chrome"}
        self.calls = []

    def connect(self):
        return "ABC123"

    def uninstall_app(self):
        self.calls.append(("uninstall", None))
        return None

    def call(self, method, arg=None):
        self.calls.append((method, arg))
        if method == "status":
            if getattr(self, "released", False):
                return {"ok": True, "deviceOwner": False, "android": "14", "appVersion": "0.1.0"}
            return {
                "ok": True, "deviceOwner": True, "locked": self.locked, "protected": True,
                "android": "14", "appVersion": "0.1.0",
                "visibleBrowsers": [] if "org.mozilla.firefox" in self.hidden
                else [{"package": "org.mozilla.firefox", "label": "Firefox"}],
                "adbApps": [],
            }
        if method == "list":
            return {"ok": True, "apps": [
                {"package": p, "label": label, "installed": True, "hidden": p in self.hidden,
                 "launchable": True, "browser": browser, "protected": False}
                for p, label, browser in (
                    ("com.android.chrome", "Chrome", True),
                    ("org.mozilla.firefox", "Firefox", True),
                    ("com.android.vending", "Google Play Butik", False),
                )
            ]}
        if method == "lock":
            self.locked = True
        elif method == "unlock":
            self.locked = False
        elif method == "hide":
            self.hidden.add(arg)
        elif method == "unhide":
            self.hidden.discard(arg)
        elif method == "release":
            self.released = True
        return {"ok": True}


@unittest.skipUnless(HAVE_SCREEN, "needs tkinter and a screen")
class GuiTest(unittest.TestCase):
    def setUp(self):
        from smartdumbphone import gui

        self.gui = gui
        self.root = tk.Tk()
        self.phone = FakePhone()
        self.app = gui.App(self.root, phone=self.phone)
        self.wait_until_idle()

    def tearDown(self):
        # Cancel pending timers so they do not fire after the window is gone, then destroy it
        # (some tests replace root.destroy to see whether the program tried to close).
        for job in self.root.tk.splitlist(self.root.tk.call("after", "info")):
            self.root.after_cancel(job)
        tk.Tk.destroy(self.root)

    def wait_until_idle(self, seconds=5):
        end = time.time() + seconds
        while time.time() < end:
            self.root.update()
            if not self.app.busy:
                return
            time.sleep(0.02)
        self.fail("the window stayed busy")

    def test_shows_status_list_and_warning(self):
        self.assertIn("Android 14", self.app.connection_var.get())
        self.assertEqual(self.app.mode_var.get(), "Åben for installation")
        self.assertEqual(set(self.app.tree.get_children()),
                         {"com.android.chrome", "org.mozilla.firefox", "com.android.vending"})
        self.assertIn("Firefox", self.app.warning_var.get())

    def test_lock_hides_play_store(self):
        self.app.store_var.set(True)
        self.app.lock()
        self.wait_until_idle()
        self.assertIn(("hide", "com.android.vending"), self.phone.calls)
        self.assertTrue(self.app.mode_var.get().startswith("Låst"))

    def test_hide_warned_apps(self):
        self.app.hide_warned()
        self.wait_until_idle()
        self.assertIn(("hide", "org.mozilla.firefox"), self.phone.calls)
        self.assertEqual(self.app.status["visibleBrowsers"], [])
        self.assertFalse(self.app.warning_frame.winfo_ismapped())

    def test_show_selected(self):
        self.app.tree.selection_set(["com.android.chrome"])
        self.app._set_selected(False)
        self.wait_until_idle()
        self.assertIn(("unhide", "com.android.chrome"), self.phone.calls)
        self.assertEqual(self.app.tree.set("com.android.chrome", "state"), "Synlig")

    def test_failed_action_refreshes_state_and_keeps_error(self):
        original = self.phone.call

        def failing_lock(method, arg=None):
            if method == "lock":
                from smartdumbphone.phone import PhoneError
                raise PhoneError("Telefonen svarede ikke i tide.")
            return original(method, arg)

        self.phone.call = failing_lock
        self.app.store_var.set(True)
        self.app.lock()
        self.wait_until_idle()
        self.wait_until_idle()
        # Play Store was hidden before the lock failed; the list must show that.
        self.assertEqual(self.app.tree.set("com.android.vending", "state"), "Skjult")
        self.assertEqual(self.app.message_var.get(), "Telefonen svarede ikke i tide.")
        self.assertEqual(self.app.mode_var.get(), "Åben for installation")

    def test_close_while_open_offers_to_lock(self):
        from unittest import mock

        destroyed = []
        self.root.destroy = lambda: destroyed.append(True)
        with mock.patch.object(self.gui.messagebox, "askyesnocancel", return_value=True):
            self.app._on_close()
        self.wait_until_idle()
        self.assertIn(("lock", None), self.phone.calls)
        self.assertEqual(destroyed, [True])

    def test_close_cancel_stays_open(self):
        from unittest import mock

        destroyed = []
        self.root.destroy = lambda: destroyed.append(True)
        with mock.patch.object(self.gui.messagebox, "askyesnocancel", return_value=None):
            self.app._on_close()
        self.assertEqual(destroyed, [])
        self.assertNotIn(("lock", None), self.phone.calls)

    def test_close_when_locked_closes_without_asking(self):
        from unittest import mock

        self.app.lock()
        self.wait_until_idle()
        destroyed = []
        self.root.destroy = lambda: destroyed.append(True)
        with mock.patch.object(self.gui.messagebox, "askyesnocancel") as ask:
            self.app._on_close()
        ask.assert_not_called()
        self.assertEqual(destroyed, [True])

    def test_release_unhides_and_uninstalls(self):
        from unittest import mock

        with mock.patch.object(self.gui.messagebox, "askyesno", return_value=True):
            self.app.release()
        self.wait_until_idle()
        self.assertIn(("release", "JA"), self.phone.calls)
        self.assertIn(("uninstall", None), self.phone.calls)
        self.assertEqual(self.app.mode_var.get(), "Appen er fjernet fra telefonen")
        self.assertIn("afinstalleret", self.app.message_var.get())

    def test_release_refused_when_not_connected(self):
        from unittest import mock

        self.app.status = {}
        with mock.patch.object(self.gui.messagebox, "askyesno") as ask:
            self.app.release()
        ask.assert_not_called()
        self.assertIn("ingen forbindelse", self.app.message_var.get())

    def test_action_error_survives_failed_refetch(self):
        from smartdumbphone.phone import PhoneError

        original = self.phone.call
        state = {"unplugged": False}

        def call(method, arg=None):
            if method == "lock":
                state["unplugged"] = True
                raise PhoneError("Telefonen svarede ikke i tide.")
            return original(method, arg)

        def connect():
            if state["unplugged"]:
                raise PhoneError("Ingen telefon fundet.")
            return "ABC123"

        self.phone.call = call
        self.phone.connect = connect
        self.app.lock()
        self.wait_until_idle()
        message = self.app.message_var.get()
        self.assertIn("Telefonen svarede ikke i tide.", message)
        self.assertIn("Ingen telefon fundet.", message)


if __name__ == "__main__":
    unittest.main()
