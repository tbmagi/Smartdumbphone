package io.github.tbmagi.smartdumbphone

import org.json.JSONArray
import org.json.JSONObject

/**
 * One rule that says "this screen must not be shown". The accessibility service watches which
 * screen is in front and, when a rule matches, presses Back (or Home) to close it.
 *
 * Rules are stored as data and edited from the PC, so they can be updated when an app changes
 * without rebuilding the phone app.
 *
 * - [pkg]:   the app the screen belongs to, e.g. "com.facebook.orca" (Messenger).
 * - [type]:  how [value] is matched. ACTIVITY_* match the screen's class name; VIEW_ID matches
 *            a view somewhere on the screen (for screens that are not their own activity).
 * - [value]: the class-name text or the view id to look for.
 * - [action]: BACK (press back) or HOME (go to the home screen).
 * - [note]:  a short Danish label shown in the PC program.
 */
data class BlockRule(
    val pkg: String,
    val type: Type,
    val value: String,
    val action: Action = Action.BACK,
    val enabled: Boolean = true,
    val note: String = "",
) {
    enum class Type { ACTIVITY_PREFIX, ACTIVITY_EXACT, ACTIVITY_CONTAINS, VIEW_ID }

    enum class Action { BACK, HOME }

    /** Whether this rule matches a screen with the given class name (activity rules only). */
    fun matchesActivity(packageName: String?, className: String?): Boolean {
        if (!enabled || packageName != pkg || className == null) return false
        return when (type) {
            Type.ACTIVITY_PREFIX -> className.startsWith(value)
            Type.ACTIVITY_EXACT -> className == value
            Type.ACTIVITY_CONTAINS -> className.contains(value)
            Type.VIEW_ID -> false
        }
    }

    fun toJson(): JSONObject = JSONObject()
        .put("package", pkg)
        .put("type", type.name)
        .put("value", value)
        .put("action", action.name)
        .put("enabled", enabled)
        .put("note", note)

    companion object {
        fun fromJson(json: JSONObject): BlockRule? {
            val pkg = json.optString("package").takeIf { it.isNotBlank() } ?: return null
            val value = json.optString("value").takeIf { it.isNotBlank() } ?: return null
            val type = runCatching { Type.valueOf(json.optString("type")) }.getOrNull() ?: return null
            val action = runCatching { Action.valueOf(json.optString("action", "BACK")) }
                .getOrDefault(Action.BACK)
            return BlockRule(pkg, type, value, action, json.optBoolean("enabled", true), json.optString("note"))
        }
    }
}

/** The set of block rules, with JSON storage and the defaults shipped with the app. */
object BlockRules {

    fun parse(text: String?): List<BlockRule> {
        if (text.isNullOrBlank()) return emptyList()
        val array = runCatching { JSONArray(text) }.getOrNull() ?: return emptyList()
        return (0 until array.length()).mapNotNull { BlockRule.fromJson(array.optJSONObject(it) ?: return@mapNotNull null) }
    }

    fun toJson(rules: List<BlockRule>): String {
        val array = JSONArray()
        for (rule in rules) array.put(rule.toJson())
        return array.toString()
    }

    /** The apps that have at least one enabled rule; these are the "guarded" apps. */
    fun guardedPackages(rules: List<BlockRule>): Set<String> =
        rules.filter { it.enabled }.map { it.pkg }.toSet()

    /** The enabled view-id rules for an app (checked against the on-screen view tree). */
    fun viewIdRules(rules: List<BlockRule>, pkg: String): List<BlockRule> =
        rules.filter { it.enabled && it.pkg == pkg && it.type == BlockRule.Type.VIEW_ID }

    /** The enabled activity rule that matches a screen, or null. */
    fun matchActivity(rules: List<BlockRule>, pkg: String?, className: String?): BlockRule? =
        rules.firstOrNull { it.matchesActivity(pkg, className) }

    /**
     * Shipped enabled by default: Messenger's built-in browser, which is how the user reaches
     * Facebook and Reels from a chat. Reels that play inside Messenger itself may need an extra
     * rule, which the PC can add after capturing that screen on the phone.
     */
    val DEFAULTS: List<BlockRule> = listOf(
        BlockRule(
            pkg = "com.facebook.orca",
            type = BlockRule.Type.ACTIVITY_PREFIX,
            value = "com.facebook.browser.",
            note = "Browser i Messenger",
        ),
        BlockRule(
            pkg = "com.facebook.orca",
            type = BlockRule.Type.ACTIVITY_PREFIX,
            value = "com.facebook.dma.dmabrowser.",
            note = "EU-browser i Messenger",
        ),
    )
}
