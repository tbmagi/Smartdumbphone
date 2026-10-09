package io.github.tbmagi.smartdumbphone

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/** Re-hides the PC's apps after a reboot, in case anything brought one back. */
class BootReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_BOOT_COMPLETED) {
            runCatching { Guard(context).reconcile() }
        }
    }
}
