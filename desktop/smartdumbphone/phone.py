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
import time
from pathlib import Path

APP_PACKAGE = "io.github.tbmagi.smartdumbphone"
URI = "content://%s.control" % APP_PACKAGE

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
        self.serial = None
        if "List of devices attached" not in result.stdout:
            # adb itself failed, e.g. its background server could not start.
            lines = [line.strip() for line in (result.stderr + "\n" + result.stdout).splitlines() if line.strip()]
            raise PhoneError(
                "adb kunne ikke starte: %s\nGenstart pc'en, eller luk andre programmer, der bruger adb."
                % (lines[-1] if lines else "intet svar")
            )
        devices = parse_devices(result.stdout)
        ready = [serial for serial, state in devices if state == "device"]
        phones = [serial for serial in ready if not serial.startswith("emulator-")]
        if len(phones) == 1:
            self.serial = phones[0]
            return self.serial
        if len(phones) > 1:
            raise PhoneError(
                "Der er sat flere telefoner til pc'en (%s). Tag de andre ud, så kun din telefon er tilsluttet."
                % ", ".join(phones)
            )
        states = {state for serial, state in devices if not serial.startswith("emulator-")}
        if "unauthorized" in states:
            raise PhoneError("Telefonen har ikke godkendt pc'en. Lås telefonen op, og tryk Tillad i beskeden om USB-fejlretning.")
        if states & {"authorizing", "connecting"}:
            raise PhoneError("Telefonen er ved at forbinde. Lås den op, og tryk Tillad, hvis den spørger.")
        if "offline" in states:
            raise PhoneError("Telefonen forbinder ikke. Tag USB-kablet ud og i igen, hvis det bliver ved.")
        if ready:
            raise PhoneError("Programmet kan kun se en emulator. Luk emulatoren i Android Studio, og sæt telefonen til.")
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

    def uninstall_app(self, attempts=4, wait_seconds=5, sleep=time.sleep):
        """Uninstalls the phone app after 'release'. Returns None, or a Danish error text.

        Android needs a moment after 'release' before it allows the uninstall, so this tries
        a few times while it answers DELETE_FAILED_DEVICE_POLICY_MANAGER.
        """
        output = ""
        for attempt in range(attempts):
            if attempt:
                sleep(wait_seconds)
            result = self._adb(["-s", self.serial, "uninstall", APP_PACKAGE], timeout=60)
            output = (result.stdout + "\n" + result.stderr).strip()
            if "Success" in output:
                return None
            if "DELETE_FAILED_DEVICE_POLICY_MANAGER" not in output:
                break
        return output.splitlines()[-1] if output else "intet svar"

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
