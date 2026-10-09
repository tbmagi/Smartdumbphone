package io.github.tbmagi.smartdumbphone

import android.app.admin.DevicePolicyManager
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.ApplicationInfo
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.UserManager
import android.provider.Telephony
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
        }
        return json
    }

    /** Every app on the phone, including hidden ones, for the PC program. */
    fun list(): JSONObject {
        notOwner()?.let { return it }
        val protected = protectedPackages()
        val browsers = activityPackages(
            Intent(Intent.ACTION_VIEW, Uri.parse("http://example.com/"))
                .addCategory(Intent.CATEGORY_BROWSABLE)
        )
        val launchable = activityPackages(
            Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        )
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
                    .put("launchable", pkg in launchable)
                    .put("browser", pkg in browsers)
                    .put("protected", pkg in protected)
            )
        }
        return ok().put("apps", apps)
    }

    fun hide(pkg: String?): JSONObject {
        notOwner()?.let { return it }
        if (pkg.isNullOrBlank()) return fail("Skriv appens pakkenavn, fx: hide com.android.chrome")
        protectedReason(pkg)?.let { return fail(it) }
        val info = appInfo(pkg) ?: return fail("Der er ingen app med pakkenavnet $pkg på telefonen.")
        // An app removed earlier with "pm uninstall --user 0" is brought back first,
        // so it ends up hidden and protected like every other hidden app.
        if (!info.isInstalledForUser() && !dpm.installExistingPackage(admin, pkg)) {
            return fail("$pkg er fjernet fra telefonen og kunne ikke hentes frem for at blive skjult. Er telefonen låst? Kør unlock først.")
        }
        wantedHidden = wantedHidden + pkg
        applyHidden(pkg)
        if (!isHidden(pkg)) {
            wantedHidden = wantedHidden - pkg
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
            return fail("$pkg er fjernet fra telefonen og kunne ikke hentes frem. Er telefonen låst? Kør unlock først.")
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
        for (pkg in wantedHidden) dpm.setUninstallBlocked(admin, pkg, false)
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
        for (pkg in wantedHidden) {
            runCatching {
                val info = appInfo(pkg)
                if (info != null && info.isInstalledForUser() && !isHidden(pkg)) applyHidden(pkg)
            }
        }
    }

    private fun applyHidden(pkg: String) {
        // Blocking uninstall also blocks "Uninstall updates" in Settings, which could
        // otherwise bring back the factory version of the app, visible again.
        dpm.setUninstallBlocked(admin, pkg, true)
        dpm.setApplicationHidden(admin, pkg, true)
    }

    private fun isHidden(pkg: String): Boolean = dpm.isApplicationHidden(admin, pkg)

    private fun notOwner(): JSONObject? =
        if (isDeviceOwner) null
        else fail("Appen er ikke device owner endnu. Følg opsætningsguiden i docs/opsaetning.md.")

    private fun protectedReason(pkg: String): String? =
        if (pkg in protectedPackages()) "$pkg kan ikke skjules, fordi telefonen skal bruge den for at virke."
        else null

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

    @Suppress("DEPRECATION")
    private fun activityPackages(intent: Intent): Set<String> =
        pm.queryIntentActivities(intent, PackageManager.MATCH_ALL)
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
