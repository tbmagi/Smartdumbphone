package io.github.tbmagi.smartdumbphone

import android.accessibilityservice.AccessibilityService
import android.graphics.Rect
import android.os.Handler
import android.os.Looper
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/**
 * Watches which screen is in front of the user and closes screens that a [BlockRule] forbids,
 * for example Messenger's built-in browser. It only ever presses Back or Home; it reads no text.
 *
 * When the user turns this service off (to escape the blocking), Guard.reconcile hides the
 * guarded apps until the service is turned on again from the PC. That reconcile runs here in
 * onServiceConnected (on) and onUnbind (off), and also at boot and on every PC status call.
 */
class BlockerService : AccessibilityService() {

    private val handler = Handler(Looper.getMainLooper())
    private var rules: List<BlockRule> = emptyList()

    // The dismiss loop presses Back repeatedly while a blocked screen stays in front, then Home.
    private var dismissing = false
    private var backCount = 0
    private var homeAction = false

    override fun onServiceConnected() {
        instance = this
        // We do not need the node cache; without this, the first tree query would make the
        // system forward events from every app to us.
        runCatching { setCacheEnabled(false) }
        reloadRules()
        // The service is on again: let guarded apps (e.g. Messenger) be visible.
        runCatching { Guard(this).reconcile() }
    }

    override fun onUnbind(intent: android.content.Intent?): Boolean {
        instance = null
        handler.removeCallbacksAndMessages(null)
        // Decides from the real setting, so a temporary unbind (e.g. 'uiautomator dump') does not
        // hide anything: reconcile only hides when our entry is gone from the setting.
        runCatching { Guard(this).reconcile() }
        return false
    }

    override fun onDestroy() {
        instance = null
        handler.removeCallbacksAndMessages(null)
        super.onDestroy()
    }

    override fun onInterrupt() {}

    /** Re-reads the rules and tells the system which apps we care about. */
    fun reloadRules() {
        rules = Guard(this).blockRules()
        val packages = BlockRules.guardedPackages(rules)
        runCatching {
            val info = serviceInfo ?: return@runCatching
            info.packageNames = if (packages.isEmpty()) null else packages.toTypedArray()
            serviceInfo = info
        }
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        if (event == null || event.eventType != AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) return
        val pkg = event.packageName?.toString() ?: return
        if (pkg == packageName) return
        val className = event.className?.toString()
        if (looksLikeActivity(className)) lastActivity = "$pkg / $className"

        val blocked = BlockRules.matchActivity(rules, pkg, className) != null || viewIdBlocked(pkg)
        if (blocked) {
            startDismiss()
        } else if (looksLikeActivity(className)) {
            // Moved to an ordinary screen: stop pressing Back.
            stopDismiss()
        }
    }

    private fun viewIdBlocked(pkg: String): Boolean {
        val idRules = BlockRules.viewIdRules(rules, pkg)
        if (idRules.isEmpty()) return false
        val root = runCatching { rootInActiveWindow }.getOrNull() ?: return false
        return idRules.any { rule ->
            runCatching { root.findAccessibilityNodeInfosByViewId(rule.value)?.isNotEmpty() == true }
                .getOrDefault(false)
        }
    }

    private fun startDismiss() {
        if (!dismissing) {
            dismissing = true
            backCount = 0
            homeAction = false
        }
        handler.removeCallbacks(dismissStep)
        handler.postDelayed(dismissStep, FIRST_DELAY_MS)
    }

    private fun stopDismiss() {
        dismissing = false
        handler.removeCallbacks(dismissStep)
    }

    private val dismissStep = object : Runnable {
        override fun run() {
            if (!dismissing) return
            if (backCount >= MAX_BACK) {
                // Back did not get us out (e.g. a tab/fragment surface); go to the home screen once.
                if (!homeAction) {
                    homeAction = true
                    runCatching { performGlobalAction(GLOBAL_ACTION_HOME) }
                }
                stopDismiss()
                return
            }
            runCatching { performGlobalAction(GLOBAL_ACTION_BACK) }
            backCount++
            // Keep going until a non-matching screen flips `dismissing` off, capped by MAX_BACK.
            handler.postDelayed(this, RECHECK_MS)
        }
    }

    private fun looksLikeActivity(className: String?): Boolean =
        className != null && className.contains('.')

    /**
     * A snapshot of the current screen for the PC, so new rules can be made when an app changes.
     * Class names, view ids, content descriptions and positions only, never the text content.
     */
    fun captureScreen(timeoutMs: Long): JSONObject {
        val result = JSONObject()
        val latch = CountDownLatch(1)
        handler.post {
            runCatching {
                val root = rootInActiveWindow
                result.put("package", root?.packageName?.toString() ?: "")
                result.put("activity", lastActivity ?: "")
                val nodes = JSONArray()
                if (root != null) collect(root, 0, nodes, intArrayOf(0))
                result.put("nodes", nodes)
            }.onFailure { result.put("error", it.javaClass.simpleName) }
            latch.countDown()
        }
        if (!latch.await(timeoutMs, TimeUnit.MILLISECONDS)) {
            return JSONObject().put("ok", false).put("error", "Kunne ikke læse skærmen i tide.")
        }
        return JSONObject().put("ok", true).put("screen", result)
    }

    private fun collect(node: AccessibilityNodeInfo, depth: Int, out: JSONArray, count: IntArray) {
        if (count[0] >= MAX_NODES || depth > MAX_DEPTH) return
        count[0]++
        val bounds = Rect().also { node.getBoundsInScreen(it) }
        val entry = JSONObject()
            .put("depth", depth)
            .put("class", node.className?.toString() ?: "")
            .put("id", node.viewIdResourceName ?: "")
            .put("desc", node.contentDescription?.toString() ?: "")
            .put("bounds", "${bounds.left},${bounds.top},${bounds.right},${bounds.bottom}")
        // Only keep nodes that could be used in a rule, to keep the dump short.
        if (entry.optString("id").isNotEmpty() || entry.optString("desc").isNotEmpty() || depth <= 2) {
            out.put(entry)
        }
        for (i in 0 until node.childCount) {
            val child = runCatching { node.getChild(i) }.getOrNull() ?: continue
            collect(child, depth + 1, out, count)
        }
    }

    companion object {
        /** Set while the service is connected; used by the PC status and the capture command. */
        @Volatile
        var instance: BlockerService? = null
            private set

        /** The last activity class name the service saw, for the capture command. */
        @Volatile
        private var lastActivity: String? = null

        private const val FIRST_DELAY_MS = 250L
        private const val RECHECK_MS = 600L
        private const val MAX_BACK = 4
        private const val MAX_NODES = 400
        private const val MAX_DEPTH = 40
    }
}
