"""The window: the phone's state and the two big buttons at the top, the app list below."""

import json
import os
import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from . import actions
from .phone import Phone, PhoneError, find_adb, program_dir

SETTINGS_FILE = program_dir() / "data" / "settings.json"
RETRY_MS = 5000

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
        if phone is None:
            adb = find_adb(program_dir())
            phone = Phone(adb) if adb else None
        self.phone = phone
        self._retry_job = None

        self._build()
        self._update_buttons()
        self.root.after(100, self._poll_results)
        if self.phone is None:
            self.connection_var.set("adb blev ikke fundet")
            self._message(
                "Programmet kan ikke finde adb. Installer Android Studio, eller læg mappen "
                "platform-tools ved siden af programmet. Se docs\\pc-program.md."
            )
        else:
            self.refresh()

    # ----- Layout -----

    def _build(self):
        root = self.root
        root.title("Smartdumbphone")
        root.geometry("920x680")
        root.minsize(720, 520)

        menu = tk.Menu(root)
        advanced = tk.Menu(menu, tearoff=False)
        advanced.add_command(label="Nødudgang: fjern det hele fra telefonen …", command=self.release)
        menu.add_cascade(label="Avanceret", menu=advanced)
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
        self.tree.tag_configure("hidden", foreground="#888888")
        self.tree.tag_configure("warning", foreground="#b00020")
        self.tree.tag_configure("fixed", foreground="#aaaaaa")
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

    def refresh(self):
        self._run(self._fetch, self._show_state, "Henter status fra telefonen …", retry=True)

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
        if not self.status.get("deviceOwner"):
            self._message("Appen styrer ikke telefonen lige nu, så der er intet at fjerne.")
            return
        confirmed = messagebox.askyesno(
            "Nødudgang",
            "Dette viser alle skjulte apps igen, fjerner alle spærringer og gør appen til en "
            "almindelig app, som du derefter kan afinstallere.\n\n"
            "Vil du bruge den igen bagefter, skal hele opsætningen laves om, og alle konti "
            "skal fjernes fra telefonen igen.\n\nVil du fortsætte?",
            icon="warning",
            default="no",
        )
        if not confirmed:
            return

        def work():
            self.phone.call("release", "JA")
            return self._fetch()

        done_text = (
            "Appen styrer ikke længere telefonen. Du kan afinstallere den med:\n"
            "adb uninstall io.github.tbmagi.smartdumbphone"
        )
        self._run(work, lambda result: self._show_state(result, done_text), "Fjerner det hele …")

    def _store_setting_changed(self):
        self.settings["hide_store_when_locked"] = self.store_var.get()
        save_settings(self.settings)

    # ----- Talking to the phone in the background -----

    def _fetch(self):
        """Runs in the background: finds the phone and reads its status and app list."""
        self.phone.connect()
        status = self.phone.call("status")
        apps = self.phone.call("list")["apps"] if status.get("deviceOwner") else []
        return status, apps

    def _run(self, work, done, busy_text, retry=False):
        if self.busy or self.phone is None:
            return
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

    def _poll_results(self):
        try:
            while True:
                done, result, error, retry = self.results.get_nowait()
                self._set_busy(False)
                if error is None:
                    done(result)
                else:
                    self._show_error(error, retry)
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

        self._fill_list()
        self._update_buttons()
        if text:
            self._message(text)
        elif not status.get("deviceOwner"):
            self._message("Appen er ikke sat op som device owner endnu. Følg docs\\opsaetning.md, trin 7.")
        else:
            self._message("")

    def _show_error(self, error, retry):
        self._message(error)
        if retry:
            # Probably not connected: show that, and try again by itself in a moment.
            self.status, self.apps = {}, []
            self.connection_var.set("Ingen forbindelse til telefonen")
            self.mode_var.set("")
            self.warning_frame.pack_forget()
            self._fill_list()
            self._retry_job = self.root.after(RETRY_MS, self._auto_retry)
            self._update_buttons()
        else:
            # The action may have stopped halfway (e.g. Play Store hidden but not locked):
            # read the phone's real state again, and keep the error visible.
            self._run(self._fetch, lambda result: self._show_state(result, error),
                      "Henter status fra telefonen …", retry=True)

    def _auto_retry(self):
        self._retry_job = None
        if not self.busy:
            self.refresh()

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
        for button in (self.lock_button, self.open_button, self.hide_button, self.show_button, self.hide_warned_button):
            button.state(["!disabled"] if ready else ["disabled"])
        self.refresh_button.state(["!disabled"] if not self.busy and self.phone else ["disabled"])

    def _message(self, text):
        self.message_var.set(text)


def _join(text, notes):
    return "\n".join([text] + list(notes))


def _enable_sharp_text_on_windows():
    if os.name != "nt":
        return
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass


def main():
    _enable_sharp_text_on_windows()
    root = tk.Tk()
    App(root)
    root.mainloop()
