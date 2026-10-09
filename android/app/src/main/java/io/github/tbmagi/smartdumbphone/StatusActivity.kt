package io.github.tbmagi.smartdumbphone

import android.app.Activity
import android.os.Bundle
import android.widget.ScrollView
import android.widget.TextView
import org.json.JSONObject

/** Shows status only. There are deliberately no buttons or settings on the phone. */
class StatusActivity : Activity() {

    private lateinit var text: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val padding = (24 * resources.displayMetrics.density).toInt()
        text = TextView(this).apply {
            setPadding(padding, padding, padding, padding)
            textSize = 18f
            setLineSpacing(0f, 1.25f)
        }
        setContentView(ScrollView(this).apply { addView(text) })
    }

    override fun onResume() {
        super.onResume()
        text.text = describe(Guard(this).status())
    }

    private fun describe(status: JSONObject): String = buildString {
        appendLine(getString(R.string.app_name))
        appendLine()
        appendLine(getString(R.string.status_intro))
        appendLine()
        if (!status.optBoolean("deviceOwner")) {
            appendLine(getString(R.string.status_not_owner))
        } else {
            appendLine(
                getString(
                    when {
                        status.optBoolean("locked") -> R.string.status_locked
                        status.optBoolean("protected") -> R.string.status_open
                        else -> R.string.status_not_locked_yet
                    }
                )
            )
            appendLine()
            val hidden = status.optJSONArray("hidden")
            val count = hidden?.length() ?: 0
            if (count == 0) {
                appendLine(getString(R.string.status_no_hidden))
            } else {
                appendLine(getString(R.string.status_hidden_header, count))
                for (i in 0 until count) {
                    val app = hidden!!.getJSONObject(i)
                    append("• ").append(app.optString("label"))
                    if (!app.optBoolean("hidden")) append(getString(R.string.status_not_hidden_yet))
                    appendLine()
                }
            }
            appendNames(status, "visibleBrowsers", R.string.status_visible_browsers)
            appendNames(status, "adbApps", R.string.status_adb_apps)
        }
        appendLine()
        if (status.optBoolean("testOnly")) appendLine(getString(R.string.status_test_mode))
        append(getString(R.string.status_version, status.optString("appVersion"), status.optString("android")))
    }

    /** Adds a warning line naming the apps in the given list, if there are any. */
    private fun StringBuilder.appendNames(status: JSONObject, key: String, textId: Int) {
        val apps = status.optJSONArray(key) ?: return
        if (apps.length() == 0) return
        val names = (0 until apps.length()).joinToString(", ") { apps.getJSONObject(it).optString("label") }
        appendLine()
        appendLine(getString(textId, names))
    }
}
