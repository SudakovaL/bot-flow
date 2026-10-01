const MENU = [
  ["Услуги", "services"], ["FAQ", "faq"], ["Оставить заявку", "lead"],
  ["ИИ-консультант", "ai"], ["Обратная связь", "feedback"],
];
const logEl = document.getElementById("log");
const buttonsEl = document.getElementById("buttons");
const inputEl = document.getElementById("input");

function makeSessionId() {
  const bytes = crypto.getRandomValues(new Uint8Array(12));
  return "s" + Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}
let sessionId = sessionStorage.getItem("sid");
if (!sessionId) { sessionId = makeSessionId(); sessionStorage.setItem("sid", sessionId); }

function addMessage(text, who) {
  const div = document.createElement("div");
  div.className = "msg " + who;
  div.textContent = text; // только текст, без HTML
  logEl.appendChild(div);
  logEl.scrollTop = logEl.scrollHeight;
}

function setButtons(list) {
  buttonsEl.replaceChildren();
  for (const b of list) {
    const el = document.createElement("button");
    el.textContent = b.label;
    el.onclick = () => send({ action: b.action }, b.label);
    buttonsEl.appendChild(el);
  }
}

async function send(payload, shownText) {
  if (shownText) addMessage(shownText, "user");
  buttonsEl.replaceChildren();
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, ...payload }),
    });
    if (!res.ok) throw new Error(res.status);
    const data = await res.json();
    data.messages.forEach((m) => addMessage(m, "bot"));
    setButtons(data.buttons);
  } catch (e) {
    addMessage("Не удалось связаться с сервером. Попробуйте ещё раз.", "bot");
  }
}

const menuEl = document.getElementById("menu");
for (const [label, action] of MENU) {
  const el = document.createElement("button");
  el.textContent = label;
  el.onclick = () => send({ action }, label);
  menuEl.appendChild(el);
}

document.getElementById("form").onsubmit = (e) => {
  e.preventDefault();
  const text = inputEl.value.trim();
  if (!text) return;
  inputEl.value = "";
  send({ message: text }, text);
};

send({ action: "menu" });
