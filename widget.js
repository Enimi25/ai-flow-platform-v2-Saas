(function () {
  function resolveWidgetScriptEl() {
    try {
      if (document.currentScript && document.currentScript.tagName === "SCRIPT") {
        return document.currentScript;
      }
    } catch (e) {}

    const scripts = document.getElementsByTagName("script");
    for (let i = scripts.length - 1; i >= 0; i--) {
      const s = scripts[i];
      const src = (s && s.getAttribute && s.getAttribute("src")) || "";
      if (src && String(src).indexOf("widget.js") !== -1) {
        return s;
      }
    }
    return null;
  }

  function getScriptCompanyId(scriptEl) {
    try {
      const v = scriptEl && scriptEl.dataset ? scriptEl.dataset.companyId : "";
      return String(v || "").trim();
    } catch (e) {
      return "";
    }
  }

  function getScriptOrigin(scriptEl) {
    try {
      const src = (scriptEl && scriptEl.getAttribute && scriptEl.getAttribute("src")) || "";
      if (!src) return "";
      return new URL(src, window.location.href).origin;
    } catch (e) {
      return "";
    }
  }

  const scriptEl = resolveWidgetScriptEl();
  const config = window.AISalesAssistantConfig || {};

  const scriptCompanyId = getScriptCompanyId(scriptEl);
  const origin = getScriptOrigin(scriptEl) || window.location.origin;

  const DEFAULT_CHAT_API = origin + "/chat";
  const DEFAULT_CREATE_LEAD_API = origin + "/create-lead";

  const API = config.apiUrl || DEFAULT_CHAT_API;
  const CREATE_LEAD_API = config.createLeadUrl || DEFAULT_CREATE_LEAD_API;

  const companyId = scriptCompanyId || config.companyId || "";
  const siteName = config.siteName || document.title || "this business";
  const businessType = config.businessType || "online business";
  const offer = config.offer || "AI Sales Assistant";
  const price = config.price || "$99/month";
  const paymentLink = config.paymentLink || "https://buy.stripe.com/test_your_payment_link";

  let isOpen = false;
  let isSending = false;
  let leadCaptured = false;

  const css = document.createElement("style");
  css.innerHTML = `
    #aiw-btn {
      position: fixed;
      right: 24px;
      bottom: 24px;
      width: 64px;
      height: 64px;
      border-radius: 50%;
      border: none;
      background: linear-gradient(135deg, #7c3aed, #4f46e5);
      color: white;
      font-size: 26px;
      cursor: pointer;
      z-index: 999999;
      box-shadow: 0 18px 55px rgba(124, 58, 237, 0.55);
      display: flex;
      align-items: center;
      justify-content: center;
      transition: transform 0.2s ease, box-shadow 0.2s ease;
    }

    #aiw-btn:hover {
      transform: translateY(-2px) scale(1.03);
      box-shadow: 0 24px 70px rgba(124, 58, 237, 0.7);
    }

    #aiw-box {
      position: fixed;
      right: 24px;
      bottom: 102px;
      width: 380px;
      height: 560px;
      background: #08080d;
      color: white;
      border-radius: 24px;
      overflow: hidden;
      z-index: 999999;
      border: 1px solid rgba(255, 255, 255, 0.1);
      box-shadow: 0 40px 130px rgba(0, 0, 0, 0.85);
      display: none;
      flex-direction: column;
      font-family: Arial, sans-serif;
    }

    #aiw-head {
      padding: 18px 18px 16px;
      background: rgba(8, 8, 13, 0.96);
      border-bottom: 1px solid rgba(255, 255, 255, 0.08);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
    }

    #aiw-head-left {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }

    #aiw-title {
      font-size: 18px;
      font-weight: 900;
      letter-spacing: -0.3px;
    }

    #aiw-online {
      color: #7cffbd;
      font-size: 12px;
      font-weight: 700;
    }

    #aiw-close {
      width: 34px;
      height: 34px;
      border-radius: 999px;
      border: 1px solid rgba(255, 255, 255, 0.12);
      background: rgba(255, 255, 255, 0.05);
      color: white;
      cursor: pointer;
      font-size: 18px;
      line-height: 1;
    }

    #aiw-messages {
      flex: 1;
      padding: 14px;
      overflow-y: auto;
      background:
        radial-gradient(circle at 80% 20%, rgba(124, 58, 237, 0.18), transparent 28%),
        #08080d;
    }

    #aiw-messages::-webkit-scrollbar {
      width: 8px;
    }

    #aiw-messages::-webkit-scrollbar-thumb {
      background: rgba(255, 255, 255, 0.14);
      border-radius: 999px;
    }

    .aiw-msg {
      margin: 10px 0;
      padding: 12px 14px;
      border-radius: 16px;
      max-width: 82%;
      font-size: 14px;
      line-height: 1.42;
      white-space: pre-wrap;
      word-wrap: break-word;
    }

    .aiw-user {
      margin-left: auto;
      color: #fff;
      background: linear-gradient(135deg, #7c3aed, #4f46e5);
      box-shadow: 0 12px 35px rgba(124, 58, 237, 0.22);
    }

    .aiw-bot {
      margin-right: auto;
      color: #e7e7f4;
      background: #171720;
      border: 1px solid rgba(255, 255, 255, 0.055);
    }

    .aiw-system {
      margin-right: auto;
      color: #b9b9c8;
      background: rgba(255, 255, 255, 0.06);
      border: 1px solid rgba(255, 255, 255, 0.08);
    }

    #aiw-quick {
      display: flex;
      gap: 8px;
      padding: 12px;
      border-top: 1px solid rgba(255, 255, 255, 0.07);
      background: #08080d;
    }

    .aiw-qbtn {
      flex: 1;
      padding: 9px 10px;
      border-radius: 999px;
      border: 1px solid rgba(255, 255, 255, 0.12);
      background: rgba(255, 255, 255, 0.045);
      color: white;
      cursor: pointer;
      font-size: 12px;
      font-weight: 800;
      transition: 0.18s ease;
    }

    .aiw-qbtn:hover {
      background: rgba(124, 58, 237, 0.18);
      border-color: rgba(124, 58, 237, 0.45);
    }

    #aiw-input-wrap {
      display: flex;
      gap: 10px;
      padding: 12px;
      border-top: 1px solid rgba(255, 255, 255, 0.07);
      background: #08080d;
    }

    #aiw-input {
      flex: 1;
      min-width: 0;
      border: 1px solid rgba(255, 255, 255, 0.1);
      background: #111118;
      color: #fff;
      outline: none;
      padding: 13px 14px;
      border-radius: 999px;
      font-size: 14px;
    }

    #aiw-input::placeholder {
      color: #777789;
    }

    #aiw-send {
      width: 46px;
      height: 46px;
      border-radius: 999px;
      border: none;
      background: linear-gradient(135deg, #7c3aed, #4f46e5);
      color: white;
      font-weight: 900;
      cursor: pointer;
      font-size: 18px;
      flex: 0 0 auto;
    }

    #aiw-send:disabled {
      opacity: 0.55;
      cursor: not-allowed;
    }

    @media (max-width: 520px) {
      #aiw-box {
        right: 14px;
        left: 14px;
        width: auto;
        height: 72vh;
        bottom: 92px;
      }

      #aiw-btn {
        right: 18px;
        bottom: 18px;
      }
    }
  `;
  document.head.appendChild(css);

  const btn = document.createElement("button");
  btn.id = "aiw-btn";
  btn.type = "button";
  btn.innerHTML = "💬";

  const box = document.createElement("div");
  box.id = "aiw-box";

  box.innerHTML = `
    <div id="aiw-head">
      <div id="aiw-head-left">
        <div id="aiw-title">AI Sales Assistant</div>
        <div id="aiw-online">Online now</div>
      </div>
      <button id="aiw-close" type="button">×</button>
    </div>

    <div id="aiw-messages"></div>

    <div id="aiw-quick">
      <button class="aiw-qbtn" type="button" data-text="Price">Price</button>
      <button class="aiw-qbtn" type="button" data-text="Book">Book</button>
      <button class="aiw-qbtn" type="button" data-text="Pay">Pay</button>
    </div>

    <div id="aiw-input-wrap">
      <input id="aiw-input" placeholder="Type your message..." autocomplete="off" />
      <button id="aiw-send" type="button">→</button>
    </div>
  `;

  document.body.appendChild(btn);
  document.body.appendChild(box);

  const messages = box.querySelector("#aiw-messages");
  const input = box.querySelector("#aiw-input");
  const sendBtn = box.querySelector("#aiw-send");
  const closeBtn = box.querySelector("#aiw-close");

  function openWidget() {
    isOpen = true;
    box.style.display = "flex";
    setTimeout(function () {
      input.focus();
    }, 100);
  }

  function closeWidget() {
    isOpen = false;
    box.style.display = "none";
  }

  function toggleWidget() {
    if (isOpen) {
      closeWidget();
    } else {
      openWidget();
    }
  }

  function addMessage(text, type) {
    const div = document.createElement("div");
    div.className = "aiw-msg " + (type === "user" ? "aiw-user" : type === "system" ? "aiw-system" : "aiw-bot");
    div.innerText = text;
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
  }

  function getCleanText(value) {
    return String(value || "").trim();
  }

  function detectEmail(text) {
    const m = String(text || "").match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[A-Za-z]{2,}/);
    return m ? m[0] : "";
  }

  function detectPhone(text) {
    const m = String(text || "").match(/(\+?\d[\d\s().-]{7,}\d)/);
    if (!m) return "";
    const raw = m[0].trim();
    // Basic normalization: keep leading + and digits only.
    const hasPlus = raw.trim().charAt(0) === "+";
    const digits = raw.replace(/[^\d]/g, "");
    if (digits.length < 8) return "";
    return (hasPlus ? "+" : "") + digits;
  }

  function detectName(text) {
    const t = String(text || "");
    const patterns = [
      /my name is\s+([a-z][a-z'\-]*(?:\s+[a-z][a-z'\-]*){0,3})/i,
      /\bi'?m\s+([a-z][a-z'\-]*(?:\s+[a-z][a-z'\-]*){0,3})/i,
      /\bthis is\s+([a-z][a-z'\-]*(?:\s+[a-z][a-z'\-]*){0,3})/i
    ];
    for (let i = 0; i < patterns.length; i++) {
      const m = t.match(patterns[i]);
      if (m && m[1]) {
        const name = m[1].trim();
        if (name.length >= 2) return name;
      }
    }
    return "";
  }

  async function maybeCaptureLead(cleanText) {
    if (leadCaptured) return;
    if (!companyId) return;

    const emailValue = detectEmail(cleanText);
    const phoneValue = detectPhone(cleanText);
    if (!emailValue && !phoneValue) return;

    const nameValue = detectName(cleanText) || "Website Visitor";

    try {
      const res = await fetch(CREATE_LEAD_API, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          companyId: companyId,
          name: nameValue,
          email: emailValue || "",
          phone: phoneValue || "",
          source: "Website Widget",
          status: "new",
          message: cleanText
        })
      });

      const data = await res.json().catch(function () { return {}; });
      if (!res.ok || (data && data.error)) return;

      leadCaptured = true;
      addMessage("Thanks — I saved your details. Our team will contact you soon.", "bot");
    } catch (e) {
      // Ignore lead capture failures; widget chat should keep working.
    }
  }

  async function sendMessage(text) {
    const cleanText = getCleanText(text);

    if (!cleanText || isSending) {
      return;
    }

    isSending = true;
    sendBtn.disabled = true;

    addMessage(cleanText, "user");

    if (!companyId) {
      addMessage(
        "Widget is missing companyId. Please embed it like: <script src=\".../widget.js\" data-company-id=\"YOUR_COMPANY_ID\"></script>",
        "system"
      );
    }

    // Capture lead in parallel if the message contains contact info.
    maybeCaptureLead(cleanText);

    try {
      const res = await fetch(API, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
       body: JSON.stringify({
  message: cleanText,
  companyId: companyId,
  siteName: siteName,
  businessType: businessType,
  offer: offer,
  price: price,
  paymentLink: paymentLink,
  source: "website widget"
})
      });

      const data = await res.json();

      if (data && data.reply) {
        addMessage(data.reply, "bot");
      } else {
        addMessage("I received your message. How can I help you next?", "bot");
      }
    } catch (error) {
      addMessage("Server error. Please try again.", "system");
    } finally {
      isSending = false;
      sendBtn.disabled = false;
      input.focus();
    }
  }

  btn.addEventListener("click", toggleWidget);
  closeBtn.addEventListener("click", closeWidget);

  sendBtn.addEventListener("click", function () {
    const text = input.value;
    input.value = "";
    sendMessage(text);
  });

  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter") {
      const text = input.value;
      input.value = "";
      sendMessage(text);
    }
  });

  box.querySelectorAll(".aiw-qbtn").forEach(function (quickBtn) {
    quickBtn.addEventListener("click", function () {
      const text = quickBtn.getAttribute("data-text");
      sendMessage(text);
    });
  });

  setTimeout(function () {
    addMessage("Hello. How can I help you with price, booking, or payment?", "bot");
  }, 500);
})();
