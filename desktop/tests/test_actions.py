import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from smartdumbphone import actions  # noqa: E402
from smartdumbphone.phone import PhoneError  # noqa: E402


class FakePhone:
    """Records commands; packages in 'refuse' make hide/unhide fail like the real app."""

    def __init__(self, refuse=()):
        self.calls = []
        self.refuse = set(refuse)

    def call(self, method, arg=None):
        self.calls.append((method, arg))
        if arg in self.refuse:
            raise PhoneError("Afvist: %s" % arg)
        return {"ok": True}


class LockTest(unittest.TestCase):
    def test_lock_hides_store_before_locking(self):
        phone = FakePhone()
        self.assertEqual(actions.lock(phone, hide_store=True), [])
        self.assertEqual(phone.calls, [("hide", "com.android.vending"), ("lock", None)])

    def test_lock_without_store(self):
        phone = FakePhone()
        actions.lock(phone, hide_store=False)
        self.assertEqual(phone.calls, [("lock", None)])

    def test_lock_still_locks_if_store_cannot_be_hidden(self):
        phone = FakePhone(refuse={"com.android.vending"})
        notes = actions.lock(phone, hide_store=True)
        self.assertEqual(phone.calls[-1], ("lock", None))
        self.assertEqual(len(notes), 1)
        self.assertIn("Play Butik", notes[0])

    def test_open_unlocks_before_showing_store(self):
        phone = FakePhone()
        actions.open_for_install(phone, show_store=True)
        self.assertEqual(phone.calls, [("unlock", None), ("unhide", "com.android.vending")])

    def test_lock_failure_is_raised(self):
        class Broken(FakePhone):
            def call(self, method, arg=None):
                if method == "lock":
                    raise PhoneError("nej")
                return super().call(method, arg)

        with self.assertRaises(PhoneError):
            actions.lock(Broken(), hide_store=True)


class SetHiddenTest(unittest.TestCase):
    def test_collects_errors_and_continues(self):
        phone = FakePhone(refuse={"b"})
        errors = actions.set_hidden(phone, ["a", "b", "c"], hidden=True)
        self.assertEqual(errors, ["Afvist: b"])
        self.assertEqual(phone.calls, [("hide", "a"), ("hide", "b"), ("hide", "c")])

    def test_show(self):
        phone = FakePhone()
        actions.set_hidden(phone, ["a"], hidden=False)
        self.assertEqual(phone.calls, [("unhide", "a")])


STATUS = {
    "deviceOwner": True,
    "locked": True,
    "protected": True,
    "visibleBrowsers": [{"package": "org.mozilla.firefox", "label": "Firefox"}],
    "adbApps": [{"package": "moe.shizuku.privileged.api", "label": "Shizuku"}],
}

APPS = [
    {"package": "com.android.chrome", "label": "Chrome", "installed": True, "hidden": True,
     "launchable": True, "browser": True, "protected": False},
    {"package": "org.mozilla.firefox", "label": "Firefox", "installed": True, "hidden": False,
     "launchable": True, "browser": True, "protected": False},
    {"package": "com.android.vending", "label": "Google Play Butik", "installed": False, "hidden": False,
     "launchable": True, "browser": False, "protected": False},
    {"package": "moe.shizuku.privileged.api", "label": "Shizuku", "installed": True, "hidden": False,
     "launchable": True, "browser": False, "protected": False},
    {"package": "com.android.providers.settings", "label": "Settings Storage", "installed": True,
     "hidden": False, "launchable": False, "browser": False, "protected": True},
    {"package": "com.android.settings", "label": "Indstillinger", "installed": True, "hidden": False,
     "launchable": True, "browser": False, "protected": True},
]


class TextTest(unittest.TestCase):
    def test_warnings(self):
        lines = actions.warnings(STATUS)
        self.assertEqual(len(lines), 2)
        self.assertIn("Firefox", lines[0])
        self.assertIn("Shizuku", lines[1])
        self.assertEqual(actions.warnings({"visibleBrowsers": [], "adbApps": []}), [])

    def test_apps_to_hide(self):
        self.assertEqual(actions.apps_to_hide(STATUS), ["org.mozilla.firefox", "moe.shizuku.privileged.api"])

    def test_mode_text(self):
        self.assertTrue(actions.mode_text(STATUS).startswith("Låst"))
        self.assertEqual(actions.mode_text(dict(STATUS, locked=False)), "Åben for installation")
        self.assertEqual(actions.mode_text(dict(STATUS, locked=False, protected=False)), "Ikke låst endnu")
        self.assertTrue(actions.mode_text({"deviceOwner": False}).startswith("Appen styrer ikke"))

    def test_friendly_error_uses_button_name(self):
        error = PhoneError("x er fjernet. Er telefonen låst? Kør unlock først.")
        self.assertTrue(actions.friendly(error).endswith("Tryk Åbn for installation først."))


class AppRowsTest(unittest.TestCase):
    def test_default_list_hides_androids_own_parts_and_sorts_by_name(self):
        rows = actions.app_rows(APPS, STATUS)
        names = [row[1] for row in rows]
        self.assertEqual(names, ["Chrome", "Firefox", "Google Play Butik", "Indstillinger", "Shizuku"])

    def test_show_all(self):
        rows = actions.app_rows(APPS, STATUS, show_all=True)
        self.assertIn("com.android.providers.settings", [row[0] for row in rows])

    def test_states_and_notes(self):
        rows = {row[0]: row for row in actions.app_rows(APPS, STATUS)}
        self.assertEqual(rows["com.android.chrome"][2], "Skjult")
        self.assertEqual(rows["org.mozilla.firefox"][2], "Synlig")
        self.assertEqual(rows["com.android.vending"][2], "Fjernet")
        self.assertIn("Browser", rows["org.mozilla.firefox"][3])
        self.assertIn("Play Butik", rows["com.android.vending"][3])
        self.assertIn("Kan styre telefonen", rows["moe.shizuku.privileged.api"][3])
        self.assertIn("Kan ikke skjules", rows["com.android.settings"][3])
        self.assertFalse(rows["com.android.settings"][4])
        self.assertTrue(rows["com.android.chrome"][4])

    def test_search_matches_name_or_package(self):
        self.assertEqual([r[0] for r in actions.app_rows(APPS, STATUS, search="fire")], ["org.mozilla.firefox"])
        self.assertEqual([r[0] for r in actions.app_rows(APPS, STATUS, search="VENDING")], ["com.android.vending"])


if __name__ == "__main__":
    unittest.main()
