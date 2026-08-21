const BRAND = {
  bg: "#091412",
  surface: "#11211d",
  line: "#22403a",
  text: "#eaf3ef",
  muted: "#93a8a1",
  accent: "#b6f24a",
  accent2: "#3ecfb2",
  ink: "#06140f",
};

export type ProposalInput = {
  name: string;
  question: string;
  siteUrl: string;
  videoUrl?: string;
  contactEmail: string;
  contactPhone?: string;
  companyLegalName?: string;
};

const PLANS = [
  { name: "Website Agent", price: "$39", per: "/month", points: ["Website chat", "Lead capture", "Calendar booking"] },
  { name: "Connected Sales", price: "$99", per: "/month", points: ["Everything above", "Messenger replies", "Shared lead workspace"], featured: true },
  { name: "Growth Partner", price: "Custom", per: "", points: ["Follow up automation", "Funnel tuning", "A share of what it closes"] },
];

function plan(entry: (typeof PLANS)[number]) {
  const border = entry.featured ? BRAND.accent : BRAND.line;
  return `
  <td width="33%" valign="top" style="padding:6px">
    <table width="100%" cellpadding="0" cellspacing="0" style="background:${BRAND.surface};border:1px solid ${border};border-radius:14px">
      <tr><td style="padding:20px">
        <div style="font:600 15px/1.2 Helvetica,Arial,sans-serif;color:${BRAND.text}">${entry.name}</div>
        <div style="font:700 28px/1.1 Helvetica,Arial,sans-serif;color:${BRAND.text};margin:10px 0 14px">${entry.price}<span style="font:400 13px Helvetica,Arial,sans-serif;color:${BRAND.muted}">${entry.per}</span></div>
        ${entry.points
          .map((point) => `<div style="font:400 13px/1.6 Helvetica,Arial,sans-serif;color:${BRAND.muted}">&#8226; ${point}</div>`)
          .join("")}
      </td></tr>
    </table>
  </td>`;
}

/** The message a prospect gets minutes after asking for a demo. */
export function proposalEmail(input: ProposalInput) {
  const video = input.videoUrl
    ? `<tr><td style="padding:0 28px 26px">
        <a href="${input.videoUrl}" style="display:block;background:${BRAND.surface};border:1px solid ${BRAND.line};border-radius:14px;padding:22px;text-decoration:none">
          <div style="font:600 15px/1.3 Helvetica,Arial,sans-serif;color:${BRAND.text}">Watch the two minute walkthrough</div>
          <div style="font:400 13px/1.5 Helvetica,Arial,sans-serif;color:${BRAND.muted};margin-top:6px">A real conversation turning into a booked appointment.</div>
          <div style="margin-top:14px;display:inline-block;background:${BRAND.accent};color:${BRAND.ink};border-radius:999px;padding:10px 18px;font:600 13px Helvetica,Arial,sans-serif">Play the video</div>
        </a>
      </td></tr>`
    : "";

  return `<!doctype html>
<html><body style="margin:0;padding:0;background:${BRAND.bg}">
<table width="100%" cellpadding="0" cellspacing="0" style="background:${BRAND.bg};padding:28px 12px">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%">

  <tr><td style="padding:8px 28px 24px">
    <span style="display:inline-block;background:${BRAND.accent};color:${BRAND.ink};border-radius:9px;padding:7px 10px;font:800 12px Helvetica,Arial,sans-serif">AI</span>
    <span style="font:700 17px Helvetica,Arial,sans-serif;color:${BRAND.text};margin-left:8px">AI FLOW</span>
  </td></tr>

  <tr><td style="padding:0 28px 20px">
    <div style="font:700 30px/1.15 Helvetica,Arial,sans-serif;color:${BRAND.text};letter-spacing:-.5px">
      ${input.name}, here is what your agent would have done.
    </div>
    <div style="font:400 15px/1.6 Helvetica,Arial,sans-serif;color:${BRAND.muted};margin-top:14px">
      You asked us: &ldquo;${input.question}&rdquo;
    </div>
    <div style="font:400 15px/1.6 Helvetica,Arial,sans-serif;color:${BRAND.text};margin-top:14px">
      An AI FLOW agent answers a question like that in about four seconds, at any hour,
      captures the contact, and offers a time in your calendar. Below is what it costs
      and how to try it on your own site.
    </div>
  </td></tr>

  ${video}

  <tr><td style="padding:0 22px 8px">
    <table width="100%" cellpadding="0" cellspacing="0"><tr>
      ${PLANS.map(plan).join("")}
    </tr></table>
  </td></tr>

  <tr><td style="padding:22px 28px 8px">
    <a href="${input.siteUrl}#demo" style="display:inline-block;background:${BRAND.accent};color:${BRAND.ink};border-radius:999px;padding:14px 26px;font:700 15px Helvetica,Arial,sans-serif;text-decoration:none">Start a free trial</a>
    <a href="${input.siteUrl}#pricing" style="display:inline-block;color:${BRAND.text};border:1px solid ${BRAND.line};border-radius:999px;padding:13px 24px;font:600 15px Helvetica,Arial,sans-serif;text-decoration:none;margin-left:8px">See full pricing</a>
  </td></tr>

  <tr><td style="padding:26px 28px 30px;border-top:1px solid ${BRAND.line};margin-top:20px">
    <div style="font:600 14px Helvetica,Arial,sans-serif;color:${BRAND.text}">Talk to a person</div>
    <div style="font:400 13px/1.7 Helvetica,Arial,sans-serif;color:${BRAND.muted};margin-top:8px">
      ${input.companyLegalName ? `${input.companyLegalName}<br>` : ""}
      <a href="mailto:${input.contactEmail}" style="color:${BRAND.accent2};text-decoration:none">${input.contactEmail}</a>
      ${input.contactPhone ? `<br>${input.contactPhone}` : ""}
      <br><a href="${input.siteUrl}" style="color:${BRAND.accent2};text-decoration:none">${input.siteUrl.replace(/^https?:\/\//, "")}</a>
    </div>
    <div style="font:400 11px/1.6 Helvetica,Arial,sans-serif;color:${BRAND.muted};margin-top:16px">
      You are getting this because you asked for a demo at ${input.siteUrl.replace(/^https?:\/\//, "")}.
      Reply with the word stop and we will not write again.
    </div>
  </td></tr>

</table>
</td></tr></table>
</body></html>`;
}
