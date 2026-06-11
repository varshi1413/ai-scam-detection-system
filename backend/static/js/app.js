// Base URL of backend
const BASE_URL = "http://127.0.0.1:5000";

// ----------------------------
// JSON helpers
// ----------------------------
async function postJSON(endpoint, data) {
    const res = await fetch(BASE_URL + endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data)
    });
    return await res.json();
}

async function getJSON(endpoint) {
    const res = await fetch(BASE_URL + endpoint);
    return await res.json();
}

// ----------------------------
// Utils
// ----------------------------
function showJSON(targetId, data) {
    document.getElementById(targetId).innerText = JSON.stringify(data, null, 2);
}

// ----------------------------
// DOM Events
// ----------------------------
window.addEventListener("DOMContentLoaded", () => {
    const analyzeBtn = document.getElementById("analyzeBtn");
    const offerResult = document.getElementById("offerResult");

    analyzeBtn.onclick = async () => {
        const offer_text = document.getElementById("offer_text").value.trim();

        if (!offer_text) {
            offerResult.innerText = "Please paste the internship offer text.";
            return;
        }

        try {
            const data = await postJSON("/analyze_offer", { offer_text });
            showJSON("offerResult", data);
        } catch (e) {
            offerResult.innerText = "Error: " + e;
        }
    };
});