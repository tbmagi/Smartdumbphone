package io.github.tbmagi.smartdumbphone

import android.app.admin.DeviceAdminReceiver
import android.content.Context
import android.content.Intent

/** Lets Android make the app device owner ("adb shell dpm set-device-owner ..."). */
class AdminReceiver : DeviceAdminReceiver() {

    override fun onEnabled(context: Context, intent: Intent) {
        // Can arrive just before Android has finished making us device owner;
        // reconcile() checks that itself, and runs again at every status call.
        runCatching { Guard(context).reconcile() }
    }
}
