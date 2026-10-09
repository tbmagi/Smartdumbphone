"""What the buttons do, kept apart from the window so it can be tested without a phone."""

from .phone import PhoneError

PLAY_STORE = "com.android.vending"


def lock(phone, hide_store):
    """Locks the phone: optionally hides Play Store first, then blocks all installs.

    Returns a list of Danish notes about things that did not work. Locking still happens
    even if Play Store could not be hidden.
    """
    notes = []
    if hide_store:
        try:
            phone.call("hide", PLAY_STORE)
        except PhoneError as e:
            notes.append("Play Butik blev ikke skjult: %s" % friendly(e))
    phone.call("lock")
    return notes


def open_for_install(phone, show_store):
    """Opens for installation, then shows Play Store (showing it may need installs allowed).

    Returns a list of Danish notes about things that did not work.
    """
    notes = []
    phone.call("unlock")
    if show_store:
        try:
            phone.call("unhide", PLAY_STORE)
        except PhoneError as e:
            notes.append("Play Butik blev ikke vist: %s" % friendly(e))
    return notes


def set_hidden(phone, packages, hidden):
    """Hides or shows several apps. Returns a list of Danish error texts (empty if all went well)."""
    errors = []
    for package in packages:
        try:
            phone.call("hide" if hidden else "unhide", package)
        except PhoneError as e:
            errors.append(friendly(e))
    return errors


def friendly(error):
    """The phone's error text, with command-line advice turned into the window's button name."""
    return str(error).replace("Kør unlock først.", "Tryk Åbn for installation først.")


def warnings(status):
    """Danish warnings about apps that could be used to get around the lock."""
    lines = []
    browsers = status.get("visibleBrowsers") or []
    if browsers:
        lines.append("Browsere, der ikke er skjult: " + _names(browsers))
    adb_apps = status.get("adbApps") or []
    if adb_apps:
        lines.append("Apps, der kan styre telefonen ligesom pc'en: " + _names(adb_apps))
    return lines


def apps_to_hide(status):
    """Package names of the visible browsers and adb apps named in the warnings."""
    return [app["package"] for app in (status.get("visibleBrowsers") or []) + (status.get("adbApps") or [])]


def mode_text(status):
    """A short Danish description of the phone's state."""
    if not status.get("deviceOwner"):
        return "Appen styrer ikke telefonen (den er ikke device owner)"
    if status.get("locked"):
        return "Låst: der kan ikke installeres eller opdateres apps"
    if status.get("protected"):
        return "Åben for installation"
    return "Ikke låst endnu"


def app_rows(apps, status, search="", show_all=False):
    """The rows for the app list, sorted by name.

    Each row is (package, name, state, note, can_hide). By default only apps a user can
    see or that are hidden are listed; show_all also lists Android's own hidden parts.
    """
    adb_packages = {app["package"] for app in (status.get("adbApps") or [])}
    search = search.strip().lower()
    rows = []
    for app in apps:
        package = app.get("package", "")
        name = app.get("label") or package
        if not show_all and not (app.get("launchable") or app.get("browser") or app.get("hidden")):
            continue
        if search and search not in name.lower() and search not in package.lower():
            continue
        if not app.get("installed", True):
            state = "Fjernet"
        elif app.get("hidden"):
            state = "Skjult"
        else:
            state = "Synlig"
        notes = []
        if app.get("browser"):
            notes.append("Browser")
        if package == PLAY_STORE:
            notes.append("Play Butik")
        if package in adb_packages:
            notes.append("Kan styre telefonen")
        if app.get("protected"):
            notes.append("Kan ikke skjules")
        rows.append((package, name, state, ", ".join(notes), not app.get("protected")))
    rows.sort(key=lambda row: (row[1].lower(), row[0]))
    return rows


def enable_blocking(phone, status):
    """Turns on in-app browser/Reels blocking.

    Enables the service in the system setting FIRST, then marks blocking as wanted, so the
    phone never needs to hide (force-stop) the guarded apps on the way in.
    """
    phone.enable_blocker(status.get("blockerComponent", ""))
    phone.call("setblocking", "on")


def disable_blocking(phone, status):
    """Turns blocking off: the service is disabled and guarded apps are shown again."""
    phone.call("setblocking", "off")
    phone.disable_blocker(status.get("blockerComponent", ""))


def blocking_state(status):
    """The blocking state, for the window's text and button.

    'off'               blocking not wanted.
    'norules'           wanted, but no rules are active.
    'on'                wanted, the service is running.
    'starting'          wanted and enabled, but the service has not reported in yet.
    'disabled_on_phone' wanted, but the service was turned off on the phone (apps hidden).
    """
    if not status.get("blockingEnabled"):
        return "off"
    if not status.get("ruleCount"):
        return "norules"
    if status.get("blockerConnected"):
        return "on"
    if status.get("blockerInSetting"):
        return "starting"
    return "disabled_on_phone"


def blocking_turn_on(state):
    """Whether pressing the toggle button should enable (rather than disable) blocking."""
    return state in ("off", "disabled_on_phone")


def blocking_button(state):
    """The toggle button's label for a state."""
    if state == "off":
        return "Slå blokering til"
    if state == "disabled_on_phone":
        return "Slå til igen"
    return "Slå blokering fra"


def blocking_text(status):
    """A Danish description of the blocking state for the window."""
    guarded = _names(status.get("guardedApps") or []) or "Messenger"
    state = blocking_state(status)
    if state == "on":
        return "Blokering er slået til. Interne browsere i %s bliver lukket automatisk." % guarded
    if state == "starting":
        return "Blokering er slået til. Tjenesten starter op på telefonen …"
    if state == "norules":
        return "Blokering er slået til, men der er ingen aktive regler, så intet bliver blokeret."
    if state == "disabled_on_phone":
        return (
            "Blokeringstjenesten er slået fra på telefonen. %s er skjult, indtil den slås til "
            "igen herfra." % guarded
        )
    return "Blokering er slået fra. Interne browsere i %s er ikke blokeret." % guarded


def capture_text(screen):
    """Turns a captured screen into readable lines, for a rule to be built from."""
    lines = [
        "Skærm gemt fra telefonen.",
        "App: %s" % screen.get("package", "?"),
        "Sidste aktivitet: %s" % screen.get("activity", "?"),
        "",
        "Elementer (klasse | id | beskrivelse | position):",
    ]
    for node in screen.get("nodes", []):
        indent = "  " * min(node.get("depth", 0), 8)
        lines.append(
            "%s%s | %s | %s | %s"
            % (indent, node.get("class", ""), node.get("id", ""), node.get("desc", ""), node.get("bounds", ""))
        )
    return "\n".join(lines)


def _names(apps):
    return ", ".join(app.get("label") or app.get("package", "?") for app in apps)
