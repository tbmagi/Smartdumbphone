"""The window: the phone's state and the two big buttons at the top, the app list below."""

import json
import os
import queue
import threading
import tkinter as tk
import traceback
from tkinter import font, messagebox, ttk

from . import actions
from .phone import Phone, PhoneError, find_adb, program_dir

SETTINGS_FILE = program_dir() / "data" / "settings.json"
RETRY_MS = 5000
SETUP_HINT = "Skal den sættes op, så følg docs\\opsaetning.md, trin 5-8."
NO_ADB = (
    "Programmet kan ikke finde adb. Installer Android Studio, eller læg mappen "
    "platform-tools ved siden af programmet, og tryk Opdater. Se docs\\pc-program.md."
)

MODE_COLORS = {
    "locked": "#1b7f3b",
    "open": "#b35c00",
    "other": "#555555",
}


def load_settings():
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_settings(settings):
    try:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    except OSError:
        pass


class App:
    def __init__(self, root, phone=None):
        self.root = root
        self.settings = load_settings()
        self.status = {}
        self.apps = []
        self.busy = False
        self.results = queue.Queue()
        self.phone = phone
        self._retry_job = None
        # An action's error, kept visible while the program re-reads the phone's state.
        self._action_error = None
        self._close_when_done = False

        self._build()
        self._update_buttons()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(100, self._poll_results)
        self.refresh()

    # ----- Layout -----

    def _build(self):
        root = self.root
        root.title("Smartdumbphone")
        root.geometry("920x680")
        root.minsize(720, 520)

        menu = tk.Menu(root)
        self.advanced_menu = tk.Menu(menu, tearoff=False)
        self.advanced_menu.add_command(label="Nødudgang: fjern det hele fra telefonen …", command=self.release)
        menu.add_cascade(label="Avanceret", menu=self.advanced_menu)
        root.config(menu=menu)

        top = ttk.Frame(root, padding=(14, 12, 14, 6))
        top.pack(fill="x")

        self.connection_var = tk.StringVar(value="Forbinder til telefonen …")
        ttk.Label(top, textvariable=self.connection_var).pack(anchor="w")

        self.mode_var = tk.StringVar(value="")
        self.mode_label = tk.Label(top, textvariable=self.mode_var, font=("Segoe UI", 15, "bold"), anchor="w")
        self.mode_label.pack(anchor="w", fill="x", pady=(4, 8))

        buttons = ttk.Frame(top)
        buttons.pack(fill="x")
        self.lock_button = ttk.Button(buttons, text="Lås telefonen", command=self.lock)
        self.lock_button.pack(side="left", ipadx=10, ipady=4)
        self.open_button = ttk.Button(buttons, text="Åbn for installation", command=self.open_for_install)
        self.open_button.pack(side="left", padx=(8, 0), ipadx=10, ipady=4)
        self.refresh_button = ttk.Button(buttons, text="Opdater", command=self.refresh)
        self.refresh_button.pack(side="right")

        self.store_var = tk.BooleanVar(value=self.settings.get("hide_store_when_locked", True))
        ttk.Checkbutton(
            top,
            text="Skjul Play Butik, når telefonen låses, og vis den, når der åbnes for installation",
            variable=self.store_var,
            command=self._store_setting_changed,
        ).pack(anchor="w", pady=(10, 0))

        self.warning_frame = ttk.Frame(top)
        self.warning_var = tk.StringVar()
        tk.Label(
            self.warning_frame, textvariable=self.warning_var, fg="#b00020", justify="left", anchor="w", wraplength=640
        ).pack(side="left", fill="x", expand=True)
        self.hide_warned_button = ttk.Button(self.warning_frame, text="Skjul dem", command=self.hide_warned)
        self.hide_warned_button.pack(side="right")

        block = ttk.LabelFrame(top, text="Blokering af interne browsere", padding=(10, 6))
        block.pack(fill="x", pady=(12, 0))
        self.block_var = tk.StringVar()
        tk.Label(block, textvariable=self.block_var, justify="left", anchor="w", wraplength=640).pack(
            anchor="w", fill="x"
        )
        block_buttons = ttk.Frame(block)
        block_buttons.pack(fill="x", pady=(6, 0))
        self.block_toggle_button = ttk.Button(block_buttons, text="Slå blokering til", command=self.toggle_blocking)
        self.block_toggle_button.pack(side="left")
        self.capture_button = ttk.Button(block_buttons, text="Gem skærmen …", command=self.capture_screen)
        self.capture_button.pack(side="left", padx=(8, 0))

        middle = ttk.Frame(root, padding=(14, 6))
        middle.pack(fill="both", expand=True)

        search_row = ttk.Frame(middle)
        search_row.pack(fill="x", pady=(0, 6))
        ttk.Label(search_row, text="Søg:").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._fill_list())
        ttk.Entry(search_row, textvariable=self.search_var, width=30).pack(side="left", padx=(6, 12))
        self.show_all_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            search_row, text="Vis også Androids egne dele", variable=self.show_all_var, command=self._fill_list
        ).pack(side="left")

        # Tk 8.6 keeps list rows 20 pixels high even on a scaled (e.g. 150 %) screen,
        # which cuts off the text. Size the rows from the font, like Tk 9 does.
        line_height = font.nametofont("TkDefaultFont").metrics("linespace")
        ttk.Style(root).configure("Treeview", rowheight=line_height + 6)

        table = ttk.Frame(middle)
        table.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(table, columns=("name", "state", "note", "package"), show="headings", selectmode="extended")
        for column, title, width in (
            ("name", "App", 220),
            ("state", "Status", 90),
            ("note", "Bemærkning", 200),
            ("package", "Pakkenavn", 300),
        ):
            self.tree.heading(column, text=title, anchor="w")
            self.tree.column(column, width=width, anchor="w")
        self.tree.tag_configure("hidden", foreground="#1f5fa8")
        self.tree.tag_configure("warning", foreground="#b00020")
        self.tree.tag_configure("fixed", foreground="#9a9a9a")
        scrollbar = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        list_buttons = ttk.Frame(middle)
        list_buttons.pack(fill="x", pady=(6, 0))
        self.hide_button = ttk.Button(list_buttons, text="Skjul valgte", command=lambda: self._set_selected(True))
        self.hide_button.pack(side="left")
        self.show_button = ttk.Button(list_buttons, text="Vis valgte", command=lambda: self._set_selected(False))
        self.show_button.pack(side="left", padx=(8, 0))

        self.message_var = tk.StringVar()
        ttk.Label(root, textvariable=self.message_var, padding=(14, 8, 14, 12), wraplength=880, justify="left").pack(
            fill="x"
        )

    # ----- Button actions -----

    def refresh(self, busy_text="Henter status fra telefonen …"):
        if self.phone is None:
            adb = find_adb(program_dir())
            if adb is None:
                self.connection_var.set("adb blev ikke fundet")
                self._message(NO_ADB)
                return
            self.phone = Phone(adb)
        self._run(self._fetch, self._show_state, busy_text, retry=True)

    def lock(self):
        hide_store = self.store_var.get()

        def work():
            notes = actions.lock(self.phone, hide_store)
            return self._fetch(), notes

        self._run(work, lambda result: self._show_state(result[0], _join("Telefonen er låst.", result[1])),
                  "Låser telefonen …")

    def open_for_install(self):
        show_store = self.store_var.get()

        def work():
            notes = actions.open_for_install(self.phone, show_store)
            return self._fetch(), notes

        done_text = "Telefonen er åben for installation. Husk at låse den igen, når du er færdig."
        self._run(work, lambda result: self._show_state(result[0], _join(done_text, result[1])),
                  "Åbner for installation …")

    def hide_warned(self):
        packages = actions.apps_to_hide(self.status)
        if packages:
            self._change_apps(packages, True)

    def toggle_blocking(self):
        status = self.status
        turn_on = actions.blocking_turn_on(actions.blocking_state(status))

        def work():
            import time as _time

            if turn_on:
                actions.enable_blocking(self.phone, status)
            else:
                actions.disable_blocking(self.phone, status)
            # The service binds/unbinds a moment later; wait (up to a few seconds) for it to settle.
            result = self._fetch()
            for _ in range(10):
                connected = result[0].get("blockerConnected")
                if (turn_on and connected) or (not turn_on and not connected):
                    break
                _time.sleep(0.5)
                result = self._fetch()
            return result

        done_text = "Blokering slået til." if turn_on else "Blokering slået fra."
        self._run(work, lambda result: self._show_state(result, done_text),
                  "Slår blokering til …" if turn_on else "Slår blokering fra …")

    def capture_screen(self):
        def work():
            answer = self.phone.call("capture")
            return answer.get("screen", {})

        def done(screen):
            path = program_dir() / "data" / "skaerm-dump.txt"
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(actions.capture_text(screen), encoding="utf-8")
                self._message(
                    "Skærmen er gemt i %s.\nÅbn Reels i Messenger, tryk Gem skærmen igen, og send "
                    "filen til mig, så laver jeg en regel." % path
                )
            except OSError as e:
                self._message("Kunne ikke gemme skærmen: %s" % e)

        self._run(work, done, "Gemmer skærmen …")

    def _set_selected(self, hidden):
        packages = list(self.tree.selection())
        if not packages:
            self._message("Vælg en eller flere apps i listen først.")
            return
        self._change_apps(packages, hidden)

    def _change_apps(self, packages, hidden):
        def work():
            errors = actions.set_hidden(self.phone, packages, hidden)
            return self._fetch(), errors

        def done(result):
            state, errors = result
            count = len(packages) - len(errors)
            text = ("Skjult" if hidden else "Vist igen") + ": %d app%s." % (count, "" if count == 1 else "s")
            if errors:
                text += "\n" + "\n".join(errors)
            self._show_state(state, text)

        self._run(work, done, "Skjuler apps …" if hidden else "Viser apps …")

    def release(self):
        if self.busy:
            self._message("Programmet er i gang med noget andet. Vent, til det er færdigt, og vælg Nødudgang igen.")
            return
        if "deviceOwner" not in self.status:
            self._message(
                "Programmet har ingen forbindelse til telefon-appen. Sæt kablet i, og tryk Opdater. "
                "Svarer appen stadig ikke, så se docs\\opsaetning.md, afsnittet Nødudgang."
            )
            return
        if not self.status.get("deviceOwner"):
            self._message("Appen styrer ikke telefonen lige nu, så der er intet at fjerne.")
            return
        confirmed = messagebox.askyesno(
            "Nødudgang",
            "Dette viser alle skjulte apps igen, fjerner alle spærringer og afinstallerer "
            "Smartdumbphone-appen fra telefonen.\n\n"
            "Vil du bruge den igen bagefter, skal hele opsætningen laves om, og alle konti "
            "skal fjernes fra telefonen igen.\n\nVil du fortsætte?",
            icon="warning",
            default="no",
        )
        if not confirmed:
            return

        component = self.status.get("blockerComponent", "")

        def work():
            self.phone.call("release", "JA")
            # Turn the accessibility service off too, so nothing is left running if the
            # uninstall below should fail.
            if component:
                try:
                    self.phone.disable_blocker(component)
                except PhoneError:
                    pass
            return self.phone.uninstall_app()

        def done(uninstall_error):
            self.status, self.apps = {}, []
            self.mode_var.set("Appen er fjernet fra telefonen")
            self.mode_label.configure(fg=MODE_COLORS["other"])
            self.warning_frame.pack_forget()
            self._fill_list()
            self._update_buttons()
            if uninstall_error:
                self._message(
                    "Appen styrer ikke længere telefonen, men den kunne ikke afinstalleres: %s\n"
                    "Se docs\\opsaetning.md, afsnittet Nødudgang." % uninstall_error
                )
            else:
                self._message("Appen styrer ikke længere telefonen og er afinstalleret. Telefonen er almindelig igen.")

        if not self._run(work, done, "Fjerner det hele …"):
            self._message("Programmet er i gang med noget andet. Vent, til det er færdigt, og vælg Nødudgang igen.")

    def _store_setting_changed(self):
        self.settings["hide_store_when_locked"] = self.store_var.get()
        save_settings(self.settings)

    def _on_close(self):
        if self.busy:
            # Closing now could stop e.g. a lock halfway; close as soon as the phone has answered.
            self._close_when_done = True
            self._message("Vent et øjeblik, programmet taler med telefonen. Vinduet lukker af sig selv bagefter.")
            return
        if self.status.get("deviceOwner") and not self.status.get("locked"):
            answer = messagebox.askyesnocancel(
                "Telefonen er ikke låst",
                "Telefonen er stadig åben for installation.\n\nVil du låse den, før du lukker?",
                icon="warning",
            )
            if answer is None:
                return
            if answer:
                self._close_when_done = True
                self.lock()
                return
        self.root.destroy()

    # ----- Talking to the phone in the background -----

    def _fetch(self):
        """Runs in the background: finds the phone and reads its status and app list."""
        self.phone.connect()
        status = self.phone.call("status")
        apps = self.phone.call("list")["apps"] if status.get("deviceOwner") else []
        return status, apps

    def _run(self, work, done, busy_text, retry=False):
        """Runs work() in the background, then done(result) in the window. False if it could not start."""
        if self.busy or self.phone is None:
            return False
        if self._retry_job is not None:
            self.root.after_cancel(self._retry_job)
            self._retry_job = None
        self._set_busy(True, busy_text)

        def target():
            try:
                self.results.put((done, work(), None, retry))
            except PhoneError as e:
                self.results.put((done, None, str(e), retry))
            except Exception as e:  # noqa: BLE001 - shown to the user instead of crashing
                self.results.put((done, None, "Uventet fejl: %s" % e, retry))

        threading.Thread(target=target, daemon=True).start()
        return True

    def _poll_results(self):
        try:
            while True:
                done, result, error, retry = self.results.get_nowait()
                self._set_busy(False)
                try:
                    if error is None:
                        done(result)
                    else:
                        self._show_error(error, retry)
                except Exception as e:  # noqa: BLE001 - keep the window working
                    self._message("Uventet fejl i programmet: %s" % e)
                if self._close_when_done and not self.busy:
                    self.root.destroy()
                    return
        except queue.Empty:
            pass
        self.root.after(100, self._poll_results)

    # ----- Showing things -----

    def _show_state(self, result, text=None):
        self.status, self.apps = result
        status = self.status
        self.connection_var.set(
            "Telefon forbundet · Android %s · app-version %s"
            % (status.get("android", "?"), status.get("appVersion", "?"))
        )
        self.mode_var.set(actions.mode_text(status))
        if status.get("deviceOwner") and status.get("locked"):
            color = MODE_COLORS["locked"]
        elif status.get("deviceOwner") and status.get("protected"):
            color = MODE_COLORS["open"]
        else:
            color = MODE_COLORS["other"]
        self.mode_label.configure(fg=color)

        lines = actions.warnings(status)
        if lines:
            self.warning_var.set("\n".join(lines))
            self.warning_frame.pack(fill="x", pady=(10, 0))
        else:
            self.warning_frame.pack_forget()

        self.block_var.set(actions.blocking_text(status))
        self.block_toggle_button.configure(text=actions.blocking_button(actions.blocking_state(status)))

        self._fill_list()
        self._update_buttons()
        if not text and not status.get("deviceOwner"):
            text = "Appen styrer ikke telefonen. " + SETUP_HINT
        self._message(_join(self._take_action_error(), [text] if text else []))

    def _show_error(self, error, retry):
        # Something went wrong: stay open so the user can see it, even if they asked to close.
        self._close_when_done = False
        if retry:
            # Probably not connected: show that, and try again by itself in a moment.
            self._message(_join(self._action_error, [error]))
            self.status, self.apps = {}, []
            self.connection_var.set("Ingen forbindelse til telefonen")
            self.mode_var.set("")
            self.warning_frame.pack_forget()
            self._fill_list()
            self._retry_job = self.root.after(RETRY_MS, self._auto_retry)
            self._update_buttons()
        else:
            # The action may have stopped halfway (e.g. Play Store hidden but not locked):
            # read the phone's real state again, and keep the error visible meanwhile.
            self._action_error = error
            self._message(error)
            self._run(self._fetch, self._show_state, None, retry=True)

    def _take_action_error(self):
        error, self._action_error = self._action_error, None
        return error

    def _auto_retry(self):
        self._retry_job = None
        if not self.busy:
            # Keep the current message on screen instead of flashing "Henter status".
            self.refresh(busy_text=None)

    def _fill_list(self):
        selected = set(self.tree.selection())
        self.tree.delete(*self.tree.get_children())
        rows = actions.app_rows(self.apps, self.status, self.search_var.get(), self.show_all_var.get())
        for package, name, state, note, can_hide in rows:
            if not can_hide:
                tag = "fixed"
            elif state != "Synlig":
                tag = "hidden"
            elif note:
                tag = "warning"
            else:
                tag = ""
            self.tree.insert("", "end", iid=package, values=(name, state, note, package), tags=(tag,))
        still_there = [package for package in selected if self.tree.exists(package)]
        if still_there:
            self.tree.selection_set(still_there)

    def _set_busy(self, busy, text=None):
        self.busy = busy
        if text:
            self._message(text)
        self.root.configure(cursor="watch" if busy else "")
        self._update_buttons()

    def _update_buttons(self):
        ready = not self.busy and bool(self.status.get("deviceOwner"))
        for button in (self.lock_button, self.open_button, self.hide_button, self.show_button,
                       self.hide_warned_button, self.block_toggle_button):
            button.state(["!disabled"] if ready else ["disabled"])
        # Capturing a screen only works while the service is actually running.
        self.capture_button.state(["!disabled"] if ready and self.status.get("blockerConnected") else ["disabled"])
        self.refresh_button.state(["disabled"] if self.busy else ["!disabled"])
        self.advanced_menu.entryconfigure(0, state="disabled" if self.busy else "normal")

    def _message(self, text):
        self.message_var.set(text)


def _join(first, more):
    return "\n".join(line for line in [first] + list(more) if line)


def _enable_sharp_text_on_windows():
    if os.name != "nt":
        return
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass


def _show_callback_error(exc, value, tb):
    # Under pyw there is no console, so errors inside the window would otherwise vanish.
    messagebox.showerror("Smartdumbphone", "Programmet fik en fejl:\n\n" + "".join(traceback.format_exception(exc, value, tb)))


def main():
    _enable_sharp_text_on_windows()
    root = tk.Tk()
    root.report_callback_exception = _show_callback_error
    App(root)
    root.mainloop()
