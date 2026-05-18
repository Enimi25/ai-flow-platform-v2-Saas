(function () {
  const DEFAULT_API = "https://repository-name-ai-sales-public.onrender.com/chat";

  const config = window.AISalesAssistantConfig || {};

  const API = config.apiUrl || DEFAULT_API;

  const companyId = config.companyId || "ai_sales_assistant_main";
  const siteName = config.siteName || document.title || "this business";
  const businessType = config.businessType || "online business";
  const offer = config.offer || "AI Sales Assistant";
  const price = config.price || "$99/month";
  const paymentLink = config.paymentLink || "https://buy.stripe.com/test_your_payment_link";

  let isOpen = false;
  let isSending = false;

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

  async function sendMessage(text) {
    const cleanText = getCleanText(text);

    if (!cleanText || isSending) {
      return;
    }

    isSending = true;
    sendBtn.disabled = true;

    addMessage(cleanText, "user");

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
