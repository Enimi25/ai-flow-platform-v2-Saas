import { NextResponse } from "next/server";

/**
 * Served to the customer's own website. It reads the company id off its own
 * script tag, so one file serves every workspace.
 */
const SOURCE = String.raw`
(function () {
  var tag = document.currentScript;
  if (!tag) return;
  var company = tag.getAttribute("data-company-id");
  if (!company) return console.warn("[AI FLOW] data-company-id is missing.");
  var origin = new URL(tag.src, location.href).origin;

  fetch(origin + "/api/widget/ping", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ companyId: company, host: location.host })
  }).catch(function () {});

  var open = false;
  var frame;

  var button = document.createElement("button");
  button.type = "button";
  button.setAttribute("aria-label", "Chat with us");
  button.style.cssText = [
    "position:fixed", "right:20px", "bottom:20px", "z-index:2147483000",
    "height:56px", "padding:0 22px", "border:0", "border-radius:999px",
    "background:linear-gradient(103deg,#b6f24a 4%,#3ecfb2 96%)", "color:#06140f",
    "font:600 15px/1 system-ui,sans-serif", "cursor:pointer",
    "box-shadow:0 14px 34px rgba(0,0,0,.28)"
  ].join(";");
  button.textContent = "Chat with us";

  button.addEventListener("click", function () {
    open = !open;
    if (!frame) {
      frame = document.createElement("iframe");
      frame.src = origin + "/embed?company=" + encodeURIComponent(company);
      frame.title = "Chat";
      frame.style.cssText = [
        "position:fixed", "right:20px", "bottom:88px", "z-index:2147483000",
        "width:min(390px,calc(100vw - 32px))", "height:min(600px,calc(100vh - 130px))",
        "border:0", "border-radius:18px", "box-shadow:0 24px 60px rgba(0,0,0,.4)"
      ].join(";");
      document.body.appendChild(frame);
    }
    frame.style.display = open ? "block" : "none";
    button.textContent = open ? "Close" : "Chat with us";
  });

  document.body.appendChild(button);
})();
`;

export async function GET() {
  return new NextResponse(SOURCE, {
    headers: {
      "Content-Type": "application/javascript; charset=utf-8",
      "Cache-Control": "public, max-age=300",
      "Access-Control-Allow-Origin": "*",
    },
  });
}
