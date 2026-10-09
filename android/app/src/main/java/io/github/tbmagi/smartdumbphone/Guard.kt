package io.github.tbmagi.smartdumbphone

import android.app.admin.DevicePolicyManager
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.ApplicationInfo
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Process
import android.os.UserManager
import android.provider.Settings
import android.provider.Telephony
import android.util.Base64
import android.telecom.TelecomManager
import android.view.inputmethod.InputMethodManager
import android.webkit.WebView
import org.json.JSONArray
import org.json.JSONObject

/**
 * Everything the app does as device owner.
 *
 * Every command returns a JSON object with "ok": true/false. On failure, "error" holds a
 * Danish text meant for the user. Android itself stores hidden apps and restrictions, so
 * nothing here has to keep running in the background.
 */
class Guard(context: Context) {

    private val ctx = context.applicationContext
    private val dpm = ctx.getSystemService(DevicePolicyManager::class.java)
    private val pm = ctx.packageManager
    private val admin = ComponentName(ctx, AdminReceiver::class.java)

    // Device-protected storage can be read right after a reboot, before the phone is unlocked.
    private val prefs = ctx.createDeviceProtectedStorageContext()
        .getSharedPreferences("guard", Context.MODE_PRIVATE)

    val isDeviceOwner: Boolean
        get() = dpm.isDeviceOwnerApp(ctx.packageName)

    /** The apps the PC has asked us to keep hidden. */
    private var wantedHidden: Set<String>
        get() = prefs.getStringSet(KEY_HIDDEN, null)?.toSet() ?: emptySet()
        set(value) {
            prefs.edit().putStringSet(KEY_HIDDEN, value).commit()
        }

    /** The screen-blocking rules, defaulting to the shipped set until the PC changes them. */
    fun blockRules(): List<BlockRule> {
        val stored = prefs.getString(KEY_RULES, null) ?: return BlockRules.DEFAULTS
        return BlockRules.parse(stored)
    }

    /** Whether the PC has asked for in-app browser blocking at all. */
    private var blockingEnabled: Boolean
        get() = prefs.getBoolean(KEY_BLOCKING, false)
        set(value) {
            prefs.edit().putBoolean(KEY_BLOCKING, value).commit()
        }

    /** Apps currently hidden by the guard (not by the PC), so they can always be shown again. */
    private var guardHidden: Set<String>
        get() = prefs.getStringSet(KEY_GUARD_HIDDEN, null)?.toSet() ?: emptySet()
        set(value) {
            prefs.edit().putStringSet(KEY_GUARD_HIDDEN, value).commit()
        }

    private val blockerComponent = ComponentName(ctx, BlockerService::class.java)

    /** True when our accessibility service is listed in the system's enabled-services setting. */
    private fun isBlockerEnabledInSetting(): Boolean {
        val value = runCatching {
            Settings.Secure.getString(ctx.contentResolver, Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES)
        }.getOrNull()
        if (value.isNullOrBlank() || value == "null") return false
        return value.split(':').any { ComponentName.unflattenFromString(it) == blockerComponent }
    }

    /** Apps that have blocking rules and must be hidden whenever the service is off. */
    private fun guardedPackages(): Set<String> = BlockRules.guardedPackages(blockRules())

    fun status(): JSONObject {
        reconcile()
        val json = ok()
            .put("deviceOwner", isDeviceOwner)
            .put("testOnly", (ctx.applicationInfo.flags and ApplicationInfo.FLAG_TEST_ONLY) != 0)
            .put("appVersion", appVersion())
            .put("android", Build.VERSION.RELEASE)
            .put("sdk", Build.VERSION.SDK_INT)
            .put("build", Build.DISPLAY)
            .put("securityPatch", Build.VERSION.SECURITY_PATCH)
        if (isDeviceOwner) {
            val restrictions = dpm.getUserRestrictions(admin)
            json.put("locked", restrictions.getBoolean(INSTALL_LOCK))
                .put("protected", PROTECTION.all { restrictions.getBoolean(it) })
            val hidden = JSONArray()
            for (pkg in wantedHidden.sorted()) {
                hidden.put(
                    JSONObject()
                        .put("package", pkg)
                        .put("label", label(pkg))
                        .put("hidden", isHidden(pkg))
                )
            }
            json.put("hidden", hidden)
            // Apps that should probably be hidden too, so the lock cannot be worked around.
            json.put("visibleBrowsers", visibleApps(browserPackages()))
            json.put("adbApps", visibleApps(ADB_APPS))
            // In-app browser / Reels blocking.
            val guarded = guardedPackages()
            json.put("blockingEnabled", blockingEnabled)
            json.put("blockerInSetting", isBlockerEnabledInSetting())
            json.put("blockerConnected", BlockerService.instance != null)
            json.put("blockerComponent", blockerComponent.flattenToString())
            json.put("ruleCount", blockRules().count { it.enabled })
            val guardedJson = JSONArray()
            for (pkg in guarded.sorted()) {
                guardedJson.put(JSONObject().put("package", pkg).put("label", label(pkg)))
            }
            json.put("guardedApps", guardedJson)
        }
        return json
    }

    fun rules(): JSONObject {
        notOwner()?.let { return it }
        val array = JSONArray()
        for (rule in blockRules()) array.put(rule.toJson())
        return ok().put("rules", array)
    }

    /** Replaces all block rules. The argument is the rules JSON, base64-encoded for adb. */
    fun setRules(base64: String?): JSONObject {
        notOwner()?.let { return it }
        if (base64.isNullOrBlank()) return fail("Der mangler regler at gemme.")
        val text = runCatching { String(Base64.decode(base64, Base64.URL_SAFE), Charsets.UTF_8) }.getOrNull()
            ?: return fail("Reglerne kunne ikke læses (base64-fejl).")
        val rules = BlockRules.parse(text)
        prefs.edit().putString(KEY_RULES, BlockRules.toJson(rules)).commit()
        // Tell a running service about the new rules, and re-apply the guard hiding.
        runCatching { BlockerService.instance?.reloadRules() }
        reconcile()
        return rules()
    }

    /** Turns in-app browser blocking on or off (the PC also enables the service separately). */
    fun setBlocking(arg: String?): JSONObject {
        notOwner()?.let { return it }
        blockingEnabled = when (arg) {
            "on" -> true
            "off" -> false
            else -> return fail("Brug setblocking on eller setblocking off.")
        }
        reconcile()
        return status()
    }

    /** A snapshot of the current screen, so the PC can build a rule. Needs the service to be on. */
    fun capture(): JSONObject {
        notOwner()?.let { return it }
        val service = BlockerService.instance
            ?: return fail("Blokeringstjenesten er ikke slået til. Slå den til fra pc'en først.")
        return service.captureScreen(CAPTURE_TIMEOUT_MS)
    }

    /** Every app on the phone, including hidden ones, for the PC program. */
    fun list(): JSONObject {
        notOwner()?.let { return it }
        val lookups = lookups()
        val apps = JSONArray()
        for (info in installedApps().sortedBy { it.packageName }) {
            val pkg = info.packageName
            apps.put(
                JSONObject()
                    .put("package", pkg)
                    .put("label", label(info))
                    .put("installed", info.isInstalledForUser())
                    .put("system", (info.flags and ApplicationInfo.FLAG_SYSTEM) != 0)
                    .put("hidden", isHidden(pkg))
                    .put("launchable", pkg in lookups.launchable)
                    .put("browser", pkg in lookups.browsers)
                    .put("protected", refuseReason(info, lookups) != null)
            )
        }
        return ok().put("apps", apps)
    }

    fun hide(pkg: String?): JSONObject {
        notOwner()?.let { return it }
        if (pkg.isNullOrBlank()) return fail("Skriv appens pakkenavn, fx: hide com.android.chrome")
        val info = appInfo(pkg) ?: return fail("Der er ingen app med pakkenavnet $pkg på telefonen.")
        refuseReason(info, lookups())?.let { return fail(it) }
        // An app removed earlier with "pm uninstall --user 0" is brought back first,
        // so it ends up hidden and protected like every other hidden app.
        if (!info.isInstalledForUser() && !dpm.installExistingPackage(admin, pkg)) {
            return fail("$pkg er fjernet fra telefonen og kunne ikke hentes frem for at blive skjult. Er telefonen låst? Åbn for installation først.")
        }
        wantedHidden = wantedHidden + pkg
        applyHidden(pkg)
        if (!isHidden(pkg)) {
            wantedHidden = wantedHidden - pkg
            // Android 14 remembers the request even when it is refused; store "not hidden" instead.
            dpm.setApplicationHidden(admin, pkg, false)
            dpm.setUninstallBlocked(admin, pkg, false)
            return fail("Android ville ikke skjule $pkg.")
        }
        return ok().put("package", pkg).put("hidden", true)
    }

    fun unhide(pkg: String?): JSONObject {
        notOwner()?.let { return it }
        if (pkg.isNullOrBlank()) return fail("Skriv appens pakkenavn, fx: unhide com.android.chrome")
        wantedHidden = wantedHidden - pkg
        val info = appInfo(pkg) ?: return fail("Der er ingen app med pakkenavnet $pkg på telefonen.")
        if (!info.isInstalledForUser() && !dpm.installExistingPackage(admin, pkg)) {
            return fail("$pkg er fjernet fra telefonen og kunne ikke hentes frem. Er telefonen låst? Åbn for installation først.")
        }
        dpm.setApplicationHidden(admin, pkg, false)
        dpm.setUninstallBlocked(admin, pkg, false)
        if (isHidden(pkg)) return fail("Android ville ikke vise $pkg igen.")
        return ok().put("package", pkg).put("hidden", false)
    }

    /** Locked: the protection below, and nothing can be installed or updated. */
    fun lock(): JSONObject {
        notOwner()?.let { return it }
        for (restriction in PROTECTION + INSTALL_LOCK) dpm.addUserRestriction(admin, restriction)
        return status()
    }

    /** Open for installation: Play Store (if visible) and adb may install, the protection stays. */
    fun unlock(): JSONObject {
        notOwner()?.let { return it }
        for (restriction in PROTECTION) dpm.addUserRestriction(admin, restriction)
        dpm.clearUserRestriction(admin, INSTALL_LOCK)
        return status()
    }

    /** Shows every app again, lifts all restrictions and stops being device owner. */
    fun release(confirm: String?): JSONObject {
        notOwner()?.let { return it }
        if (confirm != "JA") return fail("Skriv JA til sidst for at bekræfte: release JA")
        for (info in installedApps()) {
            if (info.isInstalledForUser() && isHidden(info.packageName)) {
                dpm.setApplicationHidden(admin, info.packageName, false)
            }
        }
        // Clear every uninstall block, so nothing (incl. guard-hidden apps) stays blocked
        // with no admin left to clear it.
        for (info in installedApps()) runCatching { dpm.setUninstallBlocked(admin, info.packageName, false) }
        for (restriction in PROTECTION + INSTALL_LOCK) dpm.clearUserRestriction(admin, restriction)
        prefs.edit().clear().commit()
        @Suppress("DEPRECATION") // Still works on Android 14 and is the app's own way out.
        dpm.clearDeviceOwnerApp(ctx.packageName)
        return ok().put("deviceOwner", isDeviceOwner)
    }

    /** Re-applies what the PC asked for. Runs at boot, when we become device owner and on status. */
    fun reconcile() {
        if (!isDeviceOwner) return
        // Android turns backup off when an app becomes device owner; keep the user's normal backup.
        runCatching {
            if (!dpm.isBackupServiceEnabled(admin)) dpm.setBackupServiceEnabled(admin, true)
        }
        // When blocking is wanted, guarded apps (e.g. Messenger) are hidden whenever the service
        // is off, so the in-app browser cannot be reached without the blocking in place. Only
        // apps that are safe to hide are guard-hidden; a rule naming a system app can never hide it.
        val lookups = lookups()
        val guardHide =
            if (blockingEnabled && !isBlockerEnabledInSetting()) {
                guardedPackages().filter { pkg ->
                    val info = appInfo(pkg)
                    info != null && info.isInstalledForUser() && refuseReason(info, lookups) == null
                }.toSet()
            } else {
                emptySet()
            }
        for (pkg in wantedHidden + guardHide) {
            runCatching {
                val info = appInfo(pkg)
                if (info != null && info.isInstalledForUser() && !isHidden(pkg)) applyHidden(pkg)
            }
        }
        // Show again any app the guard hid earlier that should no longer be guard-hidden (the
        // service came back on, or its rule was removed), unless the PC also asked to hide it.
        for (pkg in (guardHidden + guardHide) - guardHide) {
            if (pkg in wantedHidden) continue
            runCatching { if (isHidden(pkg)) ensureVisible(pkg) }
        }
        guardHidden = guardHide
    }

    private fun applyHidden(pkg: String) {
        // Blocking uninstall also blocks "Uninstall updates" in Settings, which could
        // otherwise bring back the factory version of the app, visible again.
        dpm.setUninstallBlocked(admin, pkg, true)
        dpm.setApplicationHidden(admin, pkg, true)
    }

    private fun ensureVisible(pkg: String) {
        dpm.setApplicationHidden(admin, pkg, false)
        dpm.setUninstallBlocked(admin, pkg, false)
    }

    private fun isHidden(pkg: String): Boolean = dpm.isApplicationHidden(admin, pkg)

    private fun notOwner(): JSONObject? =
        if (isDeviceOwner) null
        else fail("Appen er ikke device owner endnu. Følg opsætningsguiden i docs/opsaetning.md.")

    private class Lookups(
        val protected: Set<String>,
        val launchable: Set<String>,
        val browsers: Set<String>,
    )

    private fun lookups() = Lookups(
        protected = protectedPackages(),
        launchable = activityPackages(Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)),
        browsers = browserPackages(),
    )

    /**
     * Why an app must not be hidden, or null if it may be. Only apps with an icon in the app
     * drawer, and browsers, can be hidden: hiding a hidden part of Android (for example the
     * settings provider) can stop the phone from starting, and adb cannot undo it.
     */
    private fun refuseReason(info: ApplicationInfo, lookups: Lookups): String? {
        val pkg = info.packageName
        return when {
            pkg in lookups.protected ->
                "$pkg kan ikke skjules, fordi telefonen skal bruge den for at virke."
            info.uid < Process.FIRST_APPLICATION_UID || (info.flags and ApplicationInfo.FLAG_PERSISTENT) != 0 ->
                "$pkg er en del af selve Android og kan ikke skjules."
            pkg !in lookups.launchable && pkg !in lookups.browsers ->
                "$pkg har ikke noget ikon i app-oversigten. Kun apps med ikon og browsere kan skjules."
            else -> null
        }
    }

    /** The given apps that are installed and not hidden, with their names. */
    private fun visibleApps(packages: Collection<String>): JSONArray {
        val result = JSONArray()
        for (pkg in packages.sorted()) {
            val info = appInfo(pkg) ?: continue
            if (info.isInstalledForUser() && !isHidden(pkg)) {
                result.put(JSONObject().put("package", pkg).put("label", label(info)))
            }
        }
        return result
    }

    /** Apps that open any web address, i.e. browsers. */
    private fun browserPackages(): Set<String> = activityPackages(
        Intent(Intent.ACTION_VIEW, Uri.parse("http://example.com/")).addCategory(Intent.CATEGORY_BROWSABLE)
    )

    /** Apps the phone needs to work, or that MitID and banking apps depend on. */
    private fun protectedPackages(): Set<String> {
        val result = ALWAYS_PROTECTED.toMutableSet()
        result += ctx.packageName
        runCatching { WebView.getCurrentWebViewPackage()?.packageName }.getOrNull()?.let { result += it }
        result += activityPackages(Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_HOME))
        runCatching {
            ctx.getSystemService(InputMethodManager::class.java).enabledInputMethodList.map { it.packageName }
        }.getOrNull()?.let { result += it }
        runCatching { ctx.getSystemService(TelecomManager::class.java).defaultDialerPackage }
            .getOrNull()?.let { result += it }
        runCatching { Telephony.Sms.getDefaultSmsPackage(ctx) }.getOrNull()?.let { result += it }
        return result
    }

    /** Includes hidden apps and apps removed for the user, so they are still recognised. */
    @Suppress("DEPRECATION")
    private fun activityPackages(intent: Intent): Set<String> =
        pm.queryIntentActivities(
            intent,
            PackageManager.MATCH_ALL or PackageManager.MATCH_UNINSTALLED_PACKAGES or
                PackageManager.MATCH_DISABLED_COMPONENTS,
        )
            .map { it.activityInfo.packageName }
            .toSet()

    @Suppress("DEPRECATION")
    private fun installedApps(): List<ApplicationInfo> =
        pm.getInstalledApplications(PackageManager.MATCH_UNINSTALLED_PACKAGES)

    @Suppress("DEPRECATION")
    private fun appInfo(pkg: String): ApplicationInfo? =
        try {
            pm.getApplicationInfo(pkg, PackageManager.MATCH_UNINSTALLED_PACKAGES)
        } catch (e: PackageManager.NameNotFoundException) {
            null
        }

    private fun ApplicationInfo.isInstalledForUser(): Boolean =
        (flags and ApplicationInfo.FLAG_INSTALLED) != 0

    private fun label(pkg: String): String = appInfo(pkg)?.let { label(it) } ?: pkg

    private fun label(info: ApplicationInfo): String =
        runCatching { info.loadLabel(pm).toString() }.getOrDefault(info.packageName)

    @Suppress("DEPRECATION")
    private fun appVersion(): String =
        runCatching { pm.getPackageInfo(ctx.packageName, 0).versionName }.getOrNull() ?: "?"

    private fun ok(): JSONObject = JSONObject().put("ok", true)

    private fun fail(message: String): JSONObject =
        JSONObject().put("ok", false).put("error", message)

    companion object {
        private const val KEY_HIDDEN = "hidden"
        private const val KEY_RULES = "rules"
        private const val KEY_BLOCKING = "blocking"
        private const val KEY_GUARD_HIDDEN = "guardHidden"
        private const val CAPTURE_TIMEOUT_MS = 2000L

        /** On from the first lock or unlock. Only "release" removes it again. */
        val PROTECTION = listOf(
            UserManager.DISALLOW_INSTALL_UNKNOWN_SOURCES_GLOBALLY, // no APK files from Files, Messenger, mail ...
            UserManager.DISALLOW_INSTALL_UNKNOWN_SOURCES,
            UserManager.DISALLOW_ADD_USER, // a new user or guest would get its own Play Store
            UserManager.DISALLOW_USER_SWITCH,
            UserManager.DISALLOW_SAFE_BOOT,
            UserManager.DISALLOW_FACTORY_RESET, // from Settings only; recovery mode still works
        )

        /** On while locked: nothing can be installed or updated, not even by Play Store or adb. */
        const val INSTALL_LOCK = UserManager.DISALLOW_INSTALL_APPS

        /**
         * Apps that can run adb commands on the phone itself (via Wireless debugging), which
         * would let them give this app orders just like the PC.
         */
        private val ADB_APPS = listOf(
            "moe.shizuku.privileged.api",
            "com.draco.ladb",
            "com.termux",
            "in.hridayan.ashell",
            "me.piebridge.brevent",
        )

        private val ALWAYS_PROTECTED = setOf(
            "android",
            "com.android.systemui",
            "com.android.settings",
            "com.android.shell",
            "com.android.phone",
            "com.android.server.telecom",
            "com.android.providers.telephony",
            "com.android.packageinstaller",
            "com.google.android.packageinstaller",
            "com.android.permissioncontroller",
            "com.google.android.permissioncontroller",
            "com.android.webview",
            "com.google.android.webview",
            "com.google.android.trichromelibrary",
            "com.google.android.gms",
            "com.google.android.gsf",
        )
    }
}
