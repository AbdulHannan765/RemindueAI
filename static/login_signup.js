const loginTab = document.getElementById("loginTab");
const signupTab = document.getElementById("signupTab");

const loginForm = document.getElementById("loginForm");
const signupForm = document.getElementById("signupForm");

const message = document.getElementById("message");


function showLogin() {
    loginForm.classList.remove("hidden");
    signupForm.classList.add("hidden");

    loginTab.classList.add("active");
    signupTab.classList.remove("active");

    message.textContent = "";
}


function showSignup() {
    signupForm.classList.remove("hidden");
    loginForm.classList.add("hidden");

    signupTab.classList.add("active");
    loginTab.classList.remove("active");

    message.textContent = "";
}


loginTab.addEventListener("click", showLogin);
signupTab.addEventListener("click", showSignup);


// -------------------------
// Signup
// -------------------------

signupForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const username = document.getElementById(
        "signupUsername"
    ).value.trim();

    const password = document.getElementById(
        "signupPassword"
    ).value;

    try {
        const response = await fetch("/api/auth/signup", {
            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({
                username,
                password
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Signup failed");
        }

        message.textContent =
            `Account created! Your User ID is ${data.user_id}`;

        signupForm.reset();

        showLogin();

    } catch (error) {
        message.textContent = error.message;
    }
});


// -------------------------
// Login
// -------------------------

loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const username = document.getElementById(
        "loginUsername"
    ).value.trim();

    const password = document.getElementById(
        "loginPassword"
    ).value;

    try {
        const response = await fetch("/api/auth/login", {
            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({
                username,
                password
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Login failed");
        }

        localStorage.setItem(
            "access_token",
            data.access_token
        );

        localStorage.setItem(
            "user_id",
            data.user.id
        );

        localStorage.setItem(
            "username",
            data.user.username
        );

        message.textContent = "Login successful!";

        // Replace this with your dashboard route.
        window.location.href = "/dashboard";

    } catch (error) {
        message.textContent = error.message;
    }
});