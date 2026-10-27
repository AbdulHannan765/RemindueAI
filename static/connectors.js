// ========================================
// Remindue - Connectors
// ========================================

// ========================================
// AUTHENTICATION
// ========================================

function getToken() {
    return localStorage.getItem("access_token");
}

if (!getToken()) {
    window.location.replace("/");
}

const API = {
    me: "/api/auth/me",
    status: "/api/connectors/status",
    gmailConnect: "/api/gmail/connect",
    telegramStart: "/api/telegram/start",
    telegramOTP: "/api/telegram/verify-otp",
    telegram2FA: "/api/telegram/verify-2fa",
};

let telegramLoginId = null;

// ========================================
// API HELPER
// ========================================

async function apiRequest(url, options = {}) {
    const token = getToken();

    if (!token) {
        window.location.replace("/");
        throw new Error("Please log in again.");
    }

    const headers = {
        ...options.headers,
        Authorization: `Bearer ${token}`,
    };

    if (options.body !== undefined) {
        headers["Content-Type"] = "application/json";
    }

    const response = await fetch(url, {
        ...options,
        headers,
    });

    if (response.status === 401 || response.status === 403) {
        localStorage.removeItem("access_token");
        window.location.replace("/");
        throw new Error("Your session has expired.");
    }

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
        throw new Error(data.detail || "Something went wrong.");
    }

    return data;
}

// ========================================
// PAGE MESSAGE
// ========================================

function showMessage(message, isError = false) {
    const element = document.getElementById("pageMessage");

    if (!element) {
        alert(message);
        return;
    }

    element.textContent = message;
    element.classList.toggle("error", isError);
    element.classList.toggle("success", !isError);
}

// ========================================
// TELEGRAM MODAL MESSAGE
// ========================================

function showTelegramMessage(message, isError = false) {
    const element = document.getElementById("telegramModalMessage");

    if (!element) {
        alert(message);
        return;
    }

    element.textContent = message;
    element.classList.toggle("error", isError);
    element.classList.toggle("success", !isError);
}

// ========================================
// USER INFORMATION
// ========================================

async function loadUserInfo() {
    try {
        const user = await apiRequest(API.me);

        const usernameElement = document.getElementById("username");
        const avatarElement = document.getElementById("userAvatar");

        if (usernameElement) {
            usernameElement.textContent = user.username;
        }

        if (avatarElement) {
            avatarElement.textContent =
                user.username.charAt(0).toUpperCase();
        }

    } catch (error) {
        console.error(
            "Could not load user information:",
            error
        );
    }
}

// ========================================
// LOGOUT
// ========================================

function logout() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("sidebar_collapsed");

    window.location.replace("/");
}

document.getElementById("logoutBtn")
    ?.addEventListener("click", logout);

// ========================================
// CONNECTOR STATUS
// ========================================

function setStatus(elementId, lightId, connected, label) {
    const statusElement = document.getElementById(elementId);
    const lightElement = document.getElementById(lightId);

    if (statusElement) {
        statusElement.textContent = label;

        statusElement.classList.toggle("connected", connected);
        statusElement.classList.toggle("not-connected", !connected);
    }

    if (lightElement) {
        lightElement.classList.toggle("connected", connected);
        lightElement.classList.toggle("not-connected", !connected);
    }
}

async function loadConnectorStatus() {
    try {
        const data = await apiRequest(API.status);

        setStatus(
            "gmailStatus",
            "gmailLight",
            data.gmail.connected,
            data.gmail.connected
                ? `Connected: ${data.gmail.email}`
                : "Not connected"
        );

        setStatus(
            "telegramStatus",
            "telegramLight",
            data.telegram.connected,
            data.telegram.connected
                ? `Connected: ${data.telegram.phone_number}`
                : "Not connected"
        );

    } catch (error) {
        console.error(
            "Could not load connector status:",
            error
        );
    }
}

// ========================================
// GMAIL CONNECTION
// ========================================

async function connectGmail() {
    const button = document.getElementById("gmailConnectBtn");

    try {
        if (button) {
            button.disabled = true;
            button.textContent = "Connecting...";
        }

        const data = await apiRequest(API.gmailConnect, {
            method: "POST",
        });

        if (!data.authorization_url) {
            throw new Error(
                "Google authorization URL was not returned."
            );
        }

        window.location.assign(data.authorization_url);

    } catch (error) {
        showMessage(error.message, true);

        if (button) {
            button.disabled = false;
            button.innerHTML = 'Connect Gmail <span>→</span>';
        }
    }
}

document.getElementById("gmailConnectBtn")
    ?.addEventListener("click", connectGmail);

// ========================================
// TELEGRAM MODAL
// ========================================

const telegramModal = document.getElementById("telegramModal");

function openTelegramModal() {
    telegramLoginId = null;

    document.getElementById("telegramPhoneForm")?.reset();
    document.getElementById("telegramOtpForm")?.reset();
    document.getElementById("telegramPasswordForm")?.reset();

    showTelegramForm("phone");
    showTelegramMessage("");

    if (telegramModal) {
        telegramModal.style.display = "flex";
    }
}

function closeTelegramModal() {
    if (telegramModal) {
        telegramModal.style.display = "none";
    }

    telegramLoginId = null;
}

// Connect Telegram button.
document.getElementById("telegramConnectBtn")
    ?.addEventListener("click", openTelegramModal);

// Close button.
document.getElementById("closeTelegramModal")
    ?.addEventListener("click", closeTelegramModal);

// Optional Cancel buttons.
document.querySelectorAll("[data-close-telegram]")
    .forEach(button => {
        button.addEventListener("click", closeTelegramModal);
    });

// Close modal when clicking outside its content.
if (telegramModal) {
    telegramModal.addEventListener("click", event => {
        if (event.target === telegramModal) {
            closeTelegramModal();
        }
    });
}

// ========================================
// TELEGRAM FORM SWITCHING
// ========================================

function showTelegramForm(step) {
    const forms = {
        phone: "telegramPhoneForm",
        otp: "telegramOtpForm",
        password: "telegramPasswordForm",
    };

    Object.entries(forms).forEach(([name, id]) => {
        const form = document.getElementById(id);

        if (form) {
            form.classList.toggle("hidden", name !== step);
        }
    });

    const title = document.getElementById("telegramModalTitle");

    const description = document.getElementById(
        "telegramModalDescription"
    );

    if (title) {
        title.textContent =
            step === "phone"
                ? "Connect Telegram"
                : step === "otp"
                    ? "Verify Telegram OTP"
                    : "Telegram Two-Step Verification";
    }

    if (description) {
        description.textContent =
            step === "phone"
                ? "Enter your Telegram phone number with country code."
                : step === "otp"
                    ? "Enter the verification code sent by Telegram."
                    : "Enter your Telegram two-step verification password.";
    }
}

// ========================================
// TELEGRAM START LOGIN
// ========================================

async function startTelegramLogin(event) {
    event.preventDefault();

    const phoneInput = document.getElementById("telegramPhone");

    const button = document.querySelector(
        "#telegramPhoneForm button[type='submit']"
    );

    const phoneNumber = phoneInput?.value.trim();

    if (!phoneNumber) {
        showTelegramMessage(
            "Enter your Telegram phone number.",
            true
        );

        return;
    }

    try {
        if (button) {
            button.disabled = true;
            button.textContent = "Sending OTP...";
        }

        const data = await apiRequest(API.telegramStart, {
            method: "POST",
            body: JSON.stringify({
                phone_number: phoneNumber,
            }),
        });

        if (!data.login_id) {
            throw new Error(
                "Telegram login ID was not returned."
            );
        }

        telegramLoginId = data.login_id;

        showTelegramForm("otp");

        showTelegramMessage(
            "OTP sent. Check your Telegram app."
        );

    } catch (error) {
        showTelegramMessage(error.message, true);

    } finally {
        if (button) {
            button.disabled = false;
            button.textContent = "Send OTP";
        }
    }
}

document.getElementById("telegramPhoneForm")
    ?.addEventListener("submit", startTelegramLogin);

// ========================================
// TELEGRAM OTP VERIFICATION
// ========================================

async function verifyTelegramOTP(event) {
    event.preventDefault();

    const otp = document.getElementById("telegramOtp")?.value.trim();

    const button = document.querySelector(
        "#telegramOtpForm button[type='submit']"
    );

    if (!telegramLoginId) {
        showTelegramMessage(
            "Start Telegram login again.",
            true
        );

        return;
    }

    if (!otp) {
        showTelegramMessage(
            "Enter the OTP.",
            true
        );

        return;
    }

    try {
        if (button) {
            button.disabled = true;
            button.textContent = "Verifying...";
        }

        const data = await apiRequest(API.telegramOTP, {
            method: "POST",
            body: JSON.stringify({
                login_id: telegramLoginId,
                otp: otp,
            }),
        });

        if (data.requires_2fa) {
            showTelegramForm("password");

            showTelegramMessage(
                "Enter your Telegram 2FA password."
            );

            return;
        }

        if (data.status === "connected") {
            closeTelegramModal();

            await loadConnectorStatus();

            showMessage("Telegram connected successfully.");

        } else {
            showTelegramMessage(
                data.message ||
                "Telegram verification was not completed.",
                true
            );
        }

    } catch (error) {
        showTelegramMessage(error.message, true);

    } finally {
        if (button) {
            button.disabled = false;
            button.textContent = "Verify OTP";
        }
    }
}

document.getElementById("telegramOtpForm")
    ?.addEventListener("submit", verifyTelegramOTP);

// ========================================
// TELEGRAM 2FA VERIFICATION
// ========================================

async function verifyTelegram2FA(event) {
    event.preventDefault();

    const password = document.getElementById(
        "telegramPassword"
    )?.value;

    const button = document.querySelector(
        "#telegramPasswordForm button[type='submit']"
    );

    if (!telegramLoginId) {
        showTelegramMessage(
            "Start Telegram login again.",
            true
        );

        return;
    }

    if (!password) {
        showTelegramMessage(
            "Enter your Telegram 2FA password.",
            true
        );

        return;
    }

    try {
        if (button) {
            button.disabled = true;
            button.textContent = "Verifying...";
        }

        const data = await apiRequest(API.telegram2FA, {
            method: "POST",
            body: JSON.stringify({
                login_id: telegramLoginId,
                password: password,
            }),
        });

        if (data.status === "connected") {
            closeTelegramModal();

            await loadConnectorStatus();

            showMessage("Telegram connected successfully.");

        } else {
            showTelegramMessage(
                data.message ||
                "Telegram verification was not completed.",
                true
            );
        }

    } catch (error) {
        showTelegramMessage(error.message, true);

    } finally {
        if (button) {
            button.disabled = false;
            button.textContent = "Verify Password";
        }
    }
}

document.getElementById("telegramPasswordForm")
    ?.addEventListener("submit", verifyTelegram2FA);

// ========================================
// GMAIL CALLBACK FEEDBACK
// ========================================

const params = new URLSearchParams(window.location.search);

if (params.get("gmail") === "connected") {
    showMessage("Gmail connected successfully.");

    window.history.replaceState(
        {},
        document.title,
        "/connectors"
    );

} else if (params.get("gmail") === "error") {
    showMessage(
        "Gmail connection failed. Please try again.",
        true
    );

    window.history.replaceState(
        {},
        document.title,
        "/connectors"
    );
}

// ========================================
// INITIALIZE
// ========================================

async function initializeConnectorsPage() {
    await loadUserInfo();
    await loadConnectorStatus();
}

initializeConnectorsPage();