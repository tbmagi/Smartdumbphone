package io.github.tbmagi.smartdumbphone

import android.content.ContentProvider
import android.content.ContentValues
import android.database.Cursor
import android.net.Uri
import android.os.Binder
import android.os.Bundle
import android.os.Process
import org.json.JSONObject

/**
 * The only way to give the app orders. From the PC:
 *
 *   adb shell content call --uri content://io.github.tbmagi.smartdumbphone.control --method status
 *
 * Commands: status, list, hide <package>, unhide <package>, lock, unlock, release JA,
 * rules, setrules <base64 JSON>, capture.
 * The argument goes in "--arg". The answer is printed as: Result: Bundle[{json={"ok":true,...}}]
 */
class ControlProvider : ContentProvider() {

    override fun onCreate() = true

    override fun call(method: String, arg: String?, extras: Bundle?): Bundle {
        val result = if (!calledFromAdb()) {
            JSONObject().put("ok", false).put("error", "Kun adb (pc'en) må styre telefonen.")
        } else {
            val identity = Binder.clearCallingIdentity()
            try {
                run(method, arg)
            } catch (e: Exception) {
                JSONObject().put("ok", false).put("error", "Fejl på telefonen: ${e.javaClass.simpleName}: ${e.message}")
            } finally {
                Binder.restoreCallingIdentity(identity)
            }
        }
        return Bundle().apply { putString("json", result.toString()) }
    }

    /**
     * The adb shell (or root). Normal apps never run as this user id, but an adb app on the
     * phone itself (via Wireless debugging) does; status() reports such apps so they can be hidden.
     */
    private fun calledFromAdb(): Boolean {
        val uid = Binder.getCallingUid()
        return uid == Process.SHELL_UID || uid == Process.ROOT_UID
    }

    private fun run(method: String, arg: String?): JSONObject {
        val guard = Guard(requireContext())
        return when (method) {
            "status" -> guard.status()
            "list" -> guard.list()
            "hide" -> guard.hide(arg)
            "unhide" -> guard.unhide(arg)
            "lock" -> guard.lock()
            "unlock" -> guard.unlock()
            "release" -> guard.release(arg)
            "rules" -> guard.rules()
            "setrules" -> guard.setRules(arg)
            "setblocking" -> guard.setBlocking(arg)
            "capture" -> guard.capture()
            else -> JSONObject().put("ok", false)
                .put("error", "Ukendt kommando: $method.")
        }
    }

    // This provider only answers call(); there is no data to query.
    override fun query(
        uri: Uri,
        projection: Array<out String>?,
        selection: String?,
        selectionArgs: Array<out String>?,
        sortOrder: String?,
    ): Cursor? = null

    override fun getType(uri: Uri): String? = null

    override fun insert(uri: Uri, values: ContentValues?): Uri? = null

    override fun delete(uri: Uri, selection: String?, selectionArgs: Array<out String>?) = 0

    override fun update(
        uri: Uri,
        values: ContentValues?,
        selection: String?,
        selectionArgs: Array<out String>?,
    ) = 0
}
