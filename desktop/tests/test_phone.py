import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from smartdumbphone.phone import URI, Phone, PhoneError, find_adb, parse_devices, parse_result  # noqa: E402


def done(stdout="", stderr="", code=0):
    return subprocess.CompletedProcess(args=[], returncode=code, stdout=stdout, stderr=stderr)


class FakeAdb:
    """Plays back canned adb output and records the commands it was given."""

    def __init__(self, *outputs):
        self.outputs = list(outputs)
        self.commands = []

    def __call__(self, command, **kwargs):
        self.commands.append(command)
        output = self.outputs.pop(0)
        if isinstance(output, Exception):
            raise output
        return output


DEVICES_ONE = done("List of devices attached\nABC123\tdevice\n\n")


class ParseDevicesTest(unittest.TestCase):
    def test_ignores_daemon_messages(self):
        output = (
            "* daemon not running; starting now at tcp:5037\n"
            "* daemon started successfully\n"
            "List of devices attached\n"
            "ABC123\tdevice\n"
            "XYZ\tunauthorized\n"
        )
        self.assertEqual(parse_devices(output), [("ABC123", "device"), ("XYZ", "unauthorized")])

    def test_empty(self):
        self.assertEqual(parse_devices("List of devices attached\n\n"), [])


class ParseResultTest(unittest.TestCase):
    def test_plain_answer(self):
        out = 'Result: Bundle[{json={"ok":true,"locked":false}}]\n'
        self.assertEqual(parse_result(out), {"ok": True, "locked": False})

    def test_danish_letters_and_brackets_inside_json(self):
        out = 'Result: Bundle[{json={"ok":false,"error":"Låst – æøå","hidden":[{"a":1}]}}]\r\n'
        self.assertEqual(parse_result(out)["error"], "Låst – æøå")
        self.assertEqual(parse_result(out)["hidden"], [{"a": 1}])

    def test_missing_provider(self):
        with self.assertRaises(PhoneError) as e:
            parse_result("", "Error while accessing provider:io.github.tbmagi.smartdumbphone.control\njava.lang...")
        self.assertIn("Appen på telefonen svarer ikke", str(e.exception))

    def test_unauthorized(self):
        with self.assertRaises(PhoneError) as e:
            parse_result("", "error: device unauthorized.")
        self.assertIn("godkendt", str(e.exception))

    def test_unplugged(self):
        with self.assertRaises(PhoneError) as e:
            parse_result("", "adb: device 'ABC123' not found")
        self.assertIn("Ingen telefon fundet", str(e.exception))

    def test_garbage(self):
        with self.assertRaises(PhoneError):
            parse_result("Result: Bundle[{json=not json}]")


class PhoneTest(unittest.TestCase):
    def test_call_builds_command_and_returns_answer(self):
        adb = FakeAdb(DEVICES_ONE, done('Result: Bundle[{json={"ok":true,"package":"com.android.chrome"}}]\n'))
        phone = Phone("adb", run=adb)
        answer = phone.call("hide", "com.android.chrome")
        self.assertEqual(answer["package"], "com.android.chrome")
        self.assertEqual(
            adb.commands[1],
            ["adb", "-s", "ABC123", "shell", "content", "call", "--uri", URI,
             "--method", "hide", "--arg", "com.android.chrome"],
        )

    def test_refusal_becomes_error_with_phone_text(self):
        adb = FakeAdb(DEVICES_ONE, done('Result: Bundle[{json={"ok":false,"error":"Kan ikke skjules."}}]\n'))
        phone = Phone("adb", run=adb)
        with self.assertRaises(PhoneError) as e:
            phone.call("hide", "android")
        self.assertEqual(str(e.exception), "Kan ikke skjules.")

    def test_rejects_unsafe_argument(self):
        adb = FakeAdb(DEVICES_ONE)
        phone = Phone("adb", run=adb)
        with self.assertRaises(PhoneError):
            phone.call("hide", "com.x; reboot")
        self.assertEqual(len(adb.commands), 1)  # only 'adb devices', never the command

    def test_reconnects_after_failure(self):
        adb = FakeAdb(
            DEVICES_ONE,
            done("", "adb: device 'ABC123' not found"),
            DEVICES_ONE,
            done('Result: Bundle[{json={"ok":true}}]\n'),
        )
        phone = Phone("adb", run=adb)
        with self.assertRaises(PhoneError):
            phone.call("status")
        self.assertIsNone(phone.serial)
        self.assertTrue(phone.call("status")["ok"])

    def test_connect_messages(self):
        cases = [
            (done("List of devices attached\n\n"), "Ingen telefon fundet"),
            (done("List of devices attached\nA\tunauthorized\n"), "godkendt"),
            (done("List of devices attached\nA\toffline\n"), "svarer ikke"),
            (done("List of devices attached\nA\tdevice\nB\tdevice\n"), "flere telefoner"),
        ]
        for output, expected in cases:
            with self.subTest(expected=expected):
                with self.assertRaises(PhoneError) as e:
                    Phone("adb", run=FakeAdb(output)).connect()
                self.assertIn(expected, str(e.exception))

    def test_timeout(self):
        adb = FakeAdb(DEVICES_ONE, subprocess.TimeoutExpired("adb", 120))
        with self.assertRaises(PhoneError) as e:
            Phone("adb", run=adb).call("list")
        self.assertIn("i tide", str(e.exception))

    def test_adb_missing(self):
        adb = FakeAdb(FileNotFoundError())
        with self.assertRaises(PhoneError):
            Phone("C:/nope/adb.exe", run=adb).connect()


class FindAdbTest(unittest.TestCase):
    def test_prefers_platform_tools_next_to_program(self):
        with tempfile.TemporaryDirectory() as folder:
            exe = "adb.exe" if os.name == "nt" else "adb"
            tools = Path(folder) / "platform-tools"
            tools.mkdir()
            (tools / exe).write_text("")
            self.assertEqual(find_adb(folder), str(tools / exe))


if __name__ == "__main__":
    unittest.main()
