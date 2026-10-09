"""Starts the Smartdumbphone PC program: double-click start.cmd, or run 'py main.py'."""

import os
import sys
import traceback


def _show_fatal(text):
    # Shown without tkinter, so it also works if tkinter itself is what failed.
    if os.name == "nt":
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, text, "Smartdumbphone", 0x10)
    else:
        print(text, file=sys.stderr)


if __name__ == "__main__":
    try:
        from smartdumbphone.gui import main

        main()
    except Exception:  # noqa: BLE001 - the program has no console when started with pyw
        _show_fatal("Programmet stoppede med en fejl:\n\n" + traceback.format_exc())
        sys.exit(1)
