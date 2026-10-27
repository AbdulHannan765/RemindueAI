// ========================================
// Remindue Dashboard - dashboard.js
// ========================================

const token = localStorage.getItem("access_token");

if (!token) {
    window.location.replace("/");
}

const $ = (id) => {
    const element = document.getElementById(id);

    if (!element) {
        console.warn(`[Remindue] Missing element #${id}`);
        return document.createElement("div");
    }

    return element;
};

window.addEventListener("error", (event) => {
    const bar = document.createElement("div");

    bar.style.cssText =
        "position:fixed;top:0;left:0;right:0;z-index:999;padding:10px 16px;" +
        "background:#7f1d1d;color:#fff;font:14px sans-serif;";

    bar.textContent = `Dashboard script error: ${event.message}`;
    document.body.prepend(bar);
});

console.log("[Remindue] dashboard.js v4 loaded");

// ========================================
// API HELPER
// ========================================

async function apiRequest(url, options = {}) {
    const response = await fetch(url, {
        ...options,
        headers: {
            ...options.headers,
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json"
        }
    });

    if (response.status === 401 || response.status === 403) {
        localStorage.removeItem("access_token");
        window.location.replace("/");
        throw new Error("Session expired. Please log in again.");
    }

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Request failed: ${response.status}`);
    }

    return response.json();
}

// ========================================
// HELPERS
// ========================================

function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = value ?? "";
    return div.innerHTML;
}

function cssSafe(value) {
    return String(value || "")
        .toLowerCase()
        .replace(/[^a-z0-9_]/g, "");
}

let toastTimer = null;

function showToast(message, isError = false) {
    const toast = $("toast");

    toast.textContent = message;
    toast.classList.toggle("error", isError);
    toast.classList.remove("hidden");

    clearTimeout(toastTimer);

    toastTimer = setTimeout(() => {
        toast.classList.add("hidden");
    }, 3500);
}

// ========================================
// USER INFORMATION
// ========================================

async function loadUser() {
    try {
        const user = await apiRequest("/api/auth/me");

        $("username").textContent = user.username;
        $("userAvatar").textContent =
            user.username.charAt(0).toUpperCase();

    } catch (error) {
        console.error("Dashboard error:", error);
    }
}

// ========================================
// SIDEBAR OPEN / CLOSE
// ========================================

const layout = $("layout");

const savedSidebar = localStorage.getItem("sidebar_collapsed");

if (
    savedSidebar === "1" ||
    (savedSidebar === null && window.innerWidth < 800)
) {
    layout.classList.add("collapsed");
}

$("sidebarToggle").addEventListener("click", () => {
    layout.classList.toggle("collapsed");

    localStorage.setItem(
        "sidebar_collapsed",
        layout.classList.contains("collapsed") ? "1" : "0"
    );
});

// ========================================
// PAGE NAVIGATION
// ========================================

function showPage(page) {
    const isAssistant = page === "assistant";

    $("remindersPage").classList.toggle("hidden", isAssistant);
    $("assistantPage").classList.toggle("hidden", !isAssistant);
    $("remindersToolbar").classList.toggle("hidden", isAssistant);

    $("remindersNav").classList.toggle("active", !isAssistant);
    $("assistantNav").classList.toggle("active", isAssistant);

    $("pageTitle").textContent = isAssistant
        ? "AI Assistant"
        : "Reminders";

    // Allow links from other pages to open the assistant directly.
    if (isAssistant) {
        history.replaceState(null, "", "/dashboard#assistant");
        setTimeout(() => $("chatInput").focus(), 50);
    } else {
        history.replaceState(null, "", "/dashboard");
    }
}

$("remindersNav").addEventListener("click", () => {
    showPage("reminders");
});

$("assistantNav").addEventListener("click", () => {
    showPage("assistant");
});

// Support /dashboard#assistant links from connectors.html.
if (window.location.hash === "#assistant") {
    showPage("assistant");
} else {
    showPage("reminders");
}

// ========================================
// NOTIFICATIONS + CLIENT-SIDE FILTERS
// ========================================

let allNotifications = [];

async function loadNotifications() {
    const data = await apiRequest("/api/notifications");

    allNotifications = Array.isArray(data.notifications)
        ? data.notifications
        : [];

    renderNotifications();
}

function getFilters() {
    return {
        source: $("filterSource").value,
        status: $("filterStatus").value,
        type: $("filterType").value
    };
}

function updateFilterUi() {
    const filters = getFilters();

    $("filterSource").classList.toggle("active", !!filters.source);
    $("filterStatus").classList.toggle("active", !!filters.status);
    $("filterType").classList.toggle("active", !!filters.type);

    $("clearFilters").classList.toggle(
        "hidden",
        !(filters.source || filters.status || filters.type)
    );
}

function renderNotifications() {
    const filters = getFilters();
    const container = $("notifications");

    updateFilterUi();

    if (allNotifications.length === 0) {
        $("resultCount").textContent = "";

        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">🔔</div>
                <p>No reminders yet</p>
                <small>Connect Gmail or Telegram and click Sync to find reminders.</small>
            </div>`;

        return;
    }

    const filtered = allNotifications.filter((notification) => {
        const source = String(notification.source || "").toLowerCase();

        return (
            (!filters.source || source === filters.source) &&
            (!filters.status || notification.status === filters.status) &&
            (
                !filters.type ||
                (notification.category || "").toUpperCase() === filters.type
            )
        );
    });

    $("resultCount").textContent =
        `Showing ${filtered.length} of ${allNotifications.length} reminders`;

    if (filtered.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">🔍</div>
                <p>No reminders match these filters</p>
            </div>`;

        return;
    }

    container.innerHTML = filtered.map((notification) => {
        const done = notification.status === "completed";

        return `
        <article class="card ${done ? "done" : ""}">
            <p class="card-text">${escapeHtml(notification.text)}</p>

            <div class="card-bottom">
                <div class="card-meta">

                    <div class="meta-row">
                        <span class="meta-key">Source:</span>
                        <span class="pill src-${cssSafe(notification.source)}">
                            ${escapeHtml(notification.source)}
                        </span>
                    </div>

                    <div class="meta-row">
                        <span class="meta-key">Category:</span>
                        <span class="pill cat-${cssSafe(notification.category)}">
                            ${escapeHtml(notification.category || "NORMAL")}
                        </span>
                    </div>

                    <div class="meta-row">
                        <span class="meta-key">Status:</span>
                        <span class="pill st-${cssSafe(notification.status)}">
                            ${escapeHtml(notification.status)}
                        </span>
                    </div>

                    ${notification.date ? `
                    <div class="meta-row">
                        <span class="meta-key">Date:</span>
                        <span>${escapeHtml(notification.date)}</span>
                    </div>` : ""}

                    ${notification.origin ? `
                    <div class="meta-row">
                        <span class="meta-key">From:</span>
                        <span>${escapeHtml(notification.origin)}</span>
                    </div>` : ""}

                </div>

                <button
                    class="status-btn ${done ? "undo" : ""}"
                    data-key="${escapeHtml(notification.key)}"
                    data-status="${done ? "not_completed" : "completed"}"
                    type="button">
                    ${done ? "Mark not completed" : "Mark completed ✓"}
                </button>
            </div>
        </article>`;
    }).join("");
}

// Filter events
["filterSource", "filterStatus", "filterType"].forEach((id) => {
    $(id).addEventListener("change", renderNotifications);
});

// Clear filters
$("clearFilters").addEventListener("click", () => {
    $("filterSource").value = "";
    $("filterStatus").value = "";
    $("filterType").value = "";

    renderNotifications();
});

// ========================================
// CHANGE NOTIFICATION STATUS
// ========================================

$("notifications").addEventListener("click", async (event) => {
    const button = event.target.closest(".status-btn");

    if (!button) return;

    const { key, status } = button.dataset;

    button.disabled = true;

    try {
        await apiRequest(
            `/api/notifications/${encodeURIComponent(key)}/status`,
            {
                method: "PATCH",
                body: JSON.stringify({ status })
            }
        );

        const item = allNotifications.find(
            (notification) => notification.key === key
        );

        if (item) {
            item.status = status;
        }

        renderNotifications();

        showToast(
            status === "completed"
                ? "Marked as completed"
                : "Marked as not completed"
        );

    } catch (error) {
        showToast(error.message, true);
        button.disabled = false;
    }
});

// ========================================
// SYNC DROPDOWN
// ========================================

const syncMenu = $("syncMenu");
const syncBtn = $("syncBtn");

function closeMenu() {
    syncMenu.classList.add("hidden");
    syncBtn.setAttribute("aria-expanded", "false");
}

syncBtn.addEventListener("click", (event) => {
    event.stopPropagation();

    const nowHidden = syncMenu.classList.toggle("hidden");

    syncBtn.setAttribute("aria-expanded", String(!nowHidden));
});

document.addEventListener("click", closeMenu);

// ========================================
// SYNC MODAL
// ========================================

let syncMode = null;

const MODAL_INFO = {
    all: {
        title: "Sync all",
        sub: "Enter values for both Telegram and Gmail."
    },
    telegram: {
        title: "Sync Telegram",
        sub: "Choose how many recent messages to read per chat."
    },
    email: {
        title: "Sync Gmail",
        sub: "Choose how many past days of emails to read."
    }
};

function openModal(mode) {
    syncMode = mode;

    $("modalError").textContent = "";

    $("telegramField").classList.toggle("hidden", mode === "email");
    $("emailField").classList.toggle("hidden", mode === "telegram");

    $("modalTitle").textContent = MODAL_INFO[mode].title;
    $("modalSub").textContent = MODAL_INFO[mode].sub;

    $("modal").classList.remove("hidden");

    const firstInput = mode === "email"
        ? $("emailInput")
        : $("telegramInput");

    firstInput.focus();
    firstInput.select();
}

function closeModal() {
    $("modal").classList.add("hidden");
}

syncMenu.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-sync]");

    if (!button) return;

    closeMenu();
    openModal(button.dataset.sync);
});

$("modalCancel").addEventListener("click", closeModal);

$("modal").addEventListener("click", (event) => {
    if (event.target === $("modal")) {
        closeModal();
    }
});

document.addEventListener("keydown", (event) => {
    if ($("modal").classList.contains("hidden")) return;

    if (event.key === "Escape") {
        closeModal();
    }

    if (event.key === "Enter") {
        $("modalStart").click();
    }
});

// Start sync
$("modalStart").addEventListener("click", async () => {
    const payload = {};

    if (syncMode === "all" || syncMode === "telegram") {
        const messages = parseInt($("telegramInput").value, 10);

        if (!messages || messages < 1 || messages > 1000) {
            $("modalError").textContent =
                "Enter messages between 1 and 1000.";

            return;
        }

        payload.telegram_messages = messages;
    }

    if (syncMode === "all" || syncMode === "email") {
        const days = parseInt($("emailInput").value, 10);

        if (!days || days < 1 || days > 365) {
            $("modalError").textContent =
                "Enter days between 1 and 365.";

            return;
        }

        payload.email_days = days;
    }

    const startButton = $("modalStart");
    startButton.disabled = true;

    try {
        await apiRequest("/api/sync", {
            method: "POST",
            body: JSON.stringify(payload)
        });

        closeModal();
        showBanner("Sync started...");
        pollSync();

    } catch (error) {
        $("modalError").textContent = error.message;

    } finally {
        startButton.disabled = false;
    }
});

// ========================================
// SYNC PROGRESS POLLING
// ========================================

function showBanner(message, isError = false) {
    const banner = $("syncBanner");

    banner.textContent = message;
    banner.classList.toggle("error", isError);
    banner.classList.remove("hidden");
}

function setSyncing(isSyncing) {
    syncBtn.disabled = isSyncing;
    syncBtn.classList.toggle("syncing", isSyncing);

    $("syncLabel").textContent = isSyncing
        ? "Syncing..."
        : "Sync";
}

let pollTimer = null;

function pollSync() {
    clearInterval(pollTimer);

    setSyncing(true);

    pollTimer = setInterval(async () => {
        try {
            const status = await apiRequest("/api/sync/status");

            // Refresh reminders while the sync is running.
            await loadNotifications();

            if (status.running) {
                showBanner(status.message || "Syncing...");
                return;
            }

            clearInterval(pollTimer);
            pollTimer = null;

            setSyncing(false);

            const summary = status.message || "Sync completed";

            if (status.errors && status.errors.length) {
                showBanner(
                    `${summary} | ${status.errors.join(" | ")}`,
                    true
                );
            } else {
                showBanner(`Sync completed: ${summary}`);
            }

        } catch (error) {
            clearInterval(pollTimer);
            pollTimer = null;

            setSyncing(false);
            showBanner(error.message, true);
        }
    }, 4000);
}

// ========================================
// AI ASSISTANT
// ========================================

let chatIsWaiting = false;

function addChatMessage(message, sender, extraClass = "") {
    const welcome = $("chatWelcome");

    if (welcome) {
        welcome.remove();
    }

    const messageRow = document.createElement("div");
    messageRow.className = `chat-message ${sender} ${extraClass}`.trim();

    const avatar = document.createElement("div");
    avatar.className = "message-avatar";
    avatar.textContent = sender === "user" ? "U" : "R";

    const content = document.createElement("div");
    content.className = "message-content";

    // textContent prevents HTML/script injection from model responses.
    content.textContent = message;

    messageRow.appendChild(avatar);
    messageRow.appendChild(content);

    $("chatMessages").appendChild(messageRow);

    $("chatMessages").scrollTop =
        $("chatMessages").scrollHeight;

    return messageRow;
}

function extractAssistantAnswer(data) {
    // Adapt to common response field names returned by the RAG service.
    const answer =
        data.answer ??
        data.response ??
        data.message ??
        data.result?.answer ??
        data.result?.response;

    if (typeof answer === "string" && answer.trim()) {
        return answer.trim();
    }

    // If the RAG service returns a result object, show a readable fallback.
    if (typeof data.result === "string" && data.result.trim()) {
        return data.result.trim();
    }

    return "I couldn't find an answer in the response. Please try asking another question.";
}

async function askAssistant(question) {
    if (chatIsWaiting) return;

    const cleanQuestion = question.trim();

    if (cleanQuestion.length < 2) {
        showToast("Please enter a longer question.", true);
        return;
    }

    chatIsWaiting = true;

    const sendButton = $("chatSendBtn");
    const input = $("chatInput");

    sendButton.disabled = true;

    addChatMessage(cleanQuestion, "user");

    input.value = "";
    input.style.height = "auto";

    const loadingMessage = addChatMessage(
        "Thinking...",
        "assistant",
        "loading"
    );

    try {
        const data = await apiRequest("/api/rag/ask", {
            method: "POST",
            body: JSON.stringify({
                question: cleanQuestion,
                top_k: 6
            })
        });

        loadingMessage.remove();

        const answer = extractAssistantAnswer(data);

        addChatMessage(answer, "assistant");

    } catch (error) {
        loadingMessage.remove();

        addChatMessage(
            `Sorry, I couldn't process that question. ${error.message}`,
            "assistant"
        );

    } finally {
        chatIsWaiting = false;
        sendButton.disabled = false;
        input.focus();
    }
}

// Submit chat form
$("chatForm").addEventListener("submit", async (event) => {
    event.preventDefault();

    const question = $("chatInput").value;

    await askAssistant(question);
});

// Enter sends; Shift + Enter creates a new line.
$("chatInput").addEventListener("keydown", (event) => {
    if (
        event.key === "Enter" &&
        !event.shiftKey &&
        !event.isComposing
    ) {
        event.preventDefault();
        $("chatForm").requestSubmit();
    }
});

// Automatically grow textarea.
$("chatInput").addEventListener("input", () => {
    const input = $("chatInput");

    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 130)}px`;
});

// Suggested questions.
$("chatMessages").addEventListener("click", (event) => {
    const suggestion = event.target.closest(".suggestion-btn");

    if (!suggestion) return;

    askAssistant(suggestion.textContent);
});

// ========================================
// LOGOUT
// ========================================

$("logoutBtn").addEventListener("click", () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("sidebar_collapsed");

    window.location.replace("/");
});

// ========================================
// INITIALIZE
// ========================================

async function init() {
    await loadUser();

    try {
        await loadNotifications();
    } catch (error) {
        showToast(error.message, true);
    }

    // Resume progress display if a sync is already running.
    try {
        const status = await apiRequest("/api/sync/status");

        if (status.running) {
            showBanner(status.message || "Syncing...");
            pollSync();
        }

    } catch (error) {
        console.error("Could not retrieve sync status:", error);
    }
}

if (token) {
    init();
}