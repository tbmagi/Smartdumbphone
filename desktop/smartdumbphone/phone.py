"""Talks to the phone app through adb: finds adb, picks the phone and sends commands.

Every command is an 'adb shell content call' to the app's ControlProvider. The phone
answers with one line: Result: Bundle[{json={"ok":true, ...}}]
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

URI = "content://io.github.tbmagi.smartdumbphone.control"

# Package names and the "JA" confirmation are the only arguments we ever send.
# They go through the phone's shell, so nothing else is allowed in them.
_SAFE_ARG = re.compile(r"^[A-Za-z0-9._]+$")


class PhoneError(Exception):
    """A problem the user can act on. The message is Danish and shown as is."""


def find_adb(program_dir=None):
    """Returns the path to adb, or None if it cannot be found.

    Looks next to the program first (so it can run from a USB stick with its own
    platform-tools), then in PATH, then where Android Studio puts it.
    """
    exe = "adb.exe" if os.name == "nt" else "adb"
    candidates = []
    if program_dir:
        candidates.append(Path(program_dir) / "platform-tools" / exe)
    on_path = shutil.which("adb")
    if on_path:
        candidates.append(Path(on_path))
    for var in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        if os.environ.get(var):
            candidates.append(Path(os.environ[var]) / "platform-tools" / exe)
    if os.environ.get("LOCALAPPDATA"):
        candidates.append(Path(os.environ["LOCALAPPDATA"]) / "Android" / "Sdk" / "platform-tools" / exe)
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return None


def parse_devices(output):
    """Parses 'adb devices' output into a list of (serial, state)."""
    devices = []
    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith("*") or line.startswith("List of devices"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            devices.append((parts[0], parts[1]))
    return devices


def parse_result(stdout, stderr=""):
    """Turns the output of 'content call' into the phone's JSON answer (a dict).

    Raises PhoneError with a Danish explanation when the phone did not answer properly.
    """
    marker = "json="
    start = stdout.find("Result: Bundle[")
    if start < 0:
        raise PhoneError(_explain_failure(stdout + "\n" + stderr))
    begin = stdout.find(marker, start)
    end = stdout.rfind("}]")
    if begin < 0 or end < begin:
        raise PhoneError("Telefonen gav et svar, som programmet ikke forstår:\n" + stdout.strip())
    try:
        return json.loads(stdout[begin + len(marker):end])
    except ValueError:
        raise PhoneError("Telefonen gav et svar, som programmet ikke forstår:\n" + stdout.strip()) from None


def _explain_failure(output):
    text = output.lower()
    if "unauthorized" in text:
        return "Telefonen har ikke godkendt pc'en. Lås telefonen op, og tryk Tillad i beskeden om USB-fejlretning."
    if "no devices" in text or ("not found" in text and "device" in text):
        return "Ingen telefon fundet. Sæt USB-kablet i, og tjek, at USB-fejlretning er slået til."
    if "offline" in text:
        return "Telefonen svarer ikke. Tag USB-kablet ud og i igen."
    if "error while accessing provider" in text or "unknown authority" in text or "could not find provider" in text:
        return ("Appen på telefonen svarer ikke. Er Smartdumbphone-appen installeret, "
                "og er telefonen låst op efter en genstart?")
    first_line = next((line for line in output.splitlines() if line.strip()), "intet svar")
    return "Uventet svar fra telefonen: " + first_line.strip()


class Phone:
    """One phone connected over USB."""

    def __init__(self, adb_path, run=subprocess.run):
        self.adb_path = adb_path
        self.serial = None
        self._run = run

    def connect(self):
        """Finds the phone. Returns its serial number or raises PhoneError."""
        result = self._adb(["devices"], timeout=30)
        devices = parse_devices(result.stdout)
        ready = [serial for serial, state in devices if state == "device"]
        if len(ready) == 1:
            self.serial = ready[0]
            return self.serial
        self.serial = None
        if len(ready) > 1:
            raise PhoneError("Der er sat flere telefoner til pc'en. Tag de andre ud, så kun din telefon er tilsluttet.")
        states = {state for _, state in devices}
        if "unauthorized" in states:
            raise PhoneError("Telefonen har ikke godkendt pc'en. Lås telefonen op, og tryk Tillad i beskeden om USB-fejlretning.")
        if "offline" in states:
            raise PhoneError("Telefonen svarer ikke. Tag USB-kablet ud og i igen.")
        raise PhoneError("Ingen telefon fundet. Sæt USB-kablet i, og tjek, at USB-fejlretning er slået til.")

    def call(self, method, arg=None):
        """Sends one command to the app and returns its answer. Raises PhoneError on failure."""
        if self.serial is None:
            self.connect()
        args = ["-s", self.serial, "shell", "content", "call", "--uri", URI, "--method", method]
        if arg is not None:
            if not _SAFE_ARG.match(arg):
                raise PhoneError("Ugyldigt pakkenavn: " + arg)
            args += ["--arg", arg]
        result = self._adb(args, timeout=120)
        try:
            answer = parse_result(result.stdout, result.stderr)
        except PhoneError:
            # The phone may have been unplugged; find it again next time.
            self.serial = None
            raise
        if not answer.get("ok"):
            raise PhoneError(answer.get("error") or "Telefonen afviste kommandoen.")
        return answer

    def _adb(self, args, timeout):
        kwargs = {}
        if os.name == "nt":
            # Do not flash a black console window for every command.
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        try:
            return self._run(
                [self.adb_path] + args,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                **kwargs,
            )
        except FileNotFoundError:
            raise PhoneError("adb blev ikke fundet: " + self.adb_path) from None
        except subprocess.TimeoutExpired:
            self.serial = None
            raise PhoneError("Telefonen svarede ikke i tide. Tjek kablet, og prøv igen.") from None


def program_dir():
    """The folder the program runs from (also when packed as an .exe later)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent
