const B = { bg: "#091412", surface: "#11211d", line: "#22403a", text: "#eaf3ef", muted: "#93a8a1", accent: "#b6f24a", ink: "#06140f" };

export const PLATFORM_STEPS: Record<string, { label: string; steps: string[]; gotcha: string }> = {
  html: {
    label: "A hand built site",
    steps: [
      "Open the file every page shares. Usually index.html, or a template named footer, layout, or base.",
      "Scroll to the bottom and find the line that reads &lt;/body&gt;.",
      "Paste the snippet on its own line directly above &lt;/body&gt;.",
      "Save and upload the file, replacing the old one.",
      "Open the site. A chat button appears in the bottom right corner.",
    ],
    gotcha: "If the site has several HTML files, the snippet goes into each one, unless they share a single template.",
  },
  wordpress: {
    label: "WordPress",
    steps: [
      "Sign in at yoursite.com/wp-admin.",
      "Plugins &rarr; Add New Plugin, search for WPCode.",
      "Press Install Now, then Activate.",
      "Left menu: Code Snippets &rarr; Header &amp; Footer.",
      "Paste the snippet into the Footer box, not the Header box.",
      "Press Save Changes.",
    ],
    gotcha: "Do not edit theme files directly. A theme update wipes those changes and the widget goes with them.",
  },
  shopify: {
    label: "Shopify",
    steps: [
      "Online Store &rarr; Themes.",
      "On the live theme press the three dots, then Edit code.",
      "In the Layout folder open theme.liquid.",
      "Search the file for &lt;/body&gt;.",
      "Paste the snippet on the line directly above it.",
      "Press Save.",
    ],
    gotcha: "This edits a theme file. Duplicate the theme first (three dots &rarr; Duplicate) so there is a copy to fall back to.",
  },
  wix: {
    label: "Wix",
    steps: [
      "Dashboard &rarr; Settings.",
      "Scroll to Advanced &rarr; Custom Code.",
      "Press Add Custom Code.",
      "Paste the snippet and name it AI FLOW.",
      "Choose All pages, and Place Code in: Body - end.",
      "Press Apply, then publish the site.",
    ],
    gotcha: "Custom code requires a paid Wix plan. On the free plan the option is greyed out.",
  },
  webflow: {
    label: "Webflow",
    steps: [
      "Project Settings (the gear icon) &rarr; Custom Code tab.",
      "Paste the snippet into Footer Code.",
      "Press Save Changes.",
      "Press Publish and confirm the domain.",
    ],
    gotcha: "Custom code only runs on a published site. It will not show in the Designer preview.",
  },
  tilda: {
    label: "Tilda",
    steps: [
      "Site Settings &rarr; More.",
      "Find HTML code for the BODY section.",
      "Paste the snippet and save.",
      "Press Publish all pages.",
    ],
    gotcha: "Republishing one page is not enough. Use Publish all pages or the widget shows on some pages only.",
  },
  squarespace: {
    label: "Squarespace",
    steps: [
      "Settings &rarr; Advanced &rarr; Code Injection.",
      "Paste the snippet into the Footer box.",
      "Press Save.",
    ],
    gotcha: "Code Injection needs a Business plan or higher. On Personal the section is missing.",
  },
};

export function installEmail(input: { snippet: string; platform: string; fromName: string; siteUrl: string }) {
  const guide = PLATFORM_STEPS[input.platform] ?? PLATFORM_STEPS.html;
  const steps = guide.steps
    .map(
      (step, index) =>
        `<tr><td width="30" valign="top" style="padding:6px 0"><span style="display:inline-block;width:22px;height:22px;border-radius:7px;background:${B.accent};color:${B.ink};font:700 12px/22px Helvetica,Arial,sans-serif;text-align:center">${index + 1}</span></td>
         <td style="padding:6px 0;font:400 14px/1.6 Helvetica,Arial,sans-serif;color:${B.text}">${step}</td></tr>`,
    )
    .join("");

  return `<!doctype html><html><body style="margin:0;background:${B.bg}">
<table width="100%" cellpadding="0" cellspacing="0" style="background:${B.bg};padding:28px 12px"><tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%">
  <tr><td style="padding:8px 28px 22px">
    <span style="display:inline-block;background:${B.accent};color:${B.ink};border-radius:9px;padding:7px 10px;font:800 12px Helvetica,Arial,sans-serif">AI</span>
    <span style="font:700 17px Helvetica,Arial,sans-serif;color:${B.text};margin-left:8px">AI FLOW</span>
  </td></tr>

  <tr><td style="padding:0 28px 18px">
    <div style="font:700 26px/1.2 Helvetica,Arial,sans-serif;color:${B.text};letter-spacing:-.4px">One line to add to the site</div>
    <div style="font:400 14px/1.6 Helvetica,Arial,sans-serif;color:${B.muted};margin-top:12px">
      ${input.fromName} asked us to send this over. It adds a chat assistant that answers
      customers and books appointments. It takes about two minutes and changes nothing else on the site.
    </div>
  </td></tr>

  <tr><td style="padding:0 28px 20px">
    <div style="background:${B.surface};border:1px solid ${B.line};border-radius:12px;padding:16px;font:400 13px/1.6 'SFMono-Regular',Menlo,monospace;color:${B.accent};word-break:break-all">${input.snippet.replace(/</g, "&lt;").replace(/>/g, "&gt;")}</div>
  </td></tr>

  <tr><td style="padding:0 28px 20px">
    <div style="font:600 15px Helvetica,Arial,sans-serif;color:${B.text};margin-bottom:6px">${guide.label}</div>
    <table width="100%" cellpadding="0" cellspacing="0">${steps}</table>
  </td></tr>

  <tr><td style="padding:0 28px 24px">
    <div style="background:#2a1f10;color:#f0c48a;border-radius:12px;padding:14px 16px;font:400 13px/1.6 Helvetica,Arial,sans-serif">
      ${guide.gotcha}
    </div>
  </td></tr>

  <tr><td style="padding:18px 28px 30px;border-top:1px solid ${B.line}">
    <div style="font:400 13px/1.7 Helvetica,Arial,sans-serif;color:${B.muted}">
      Once it is live the dashboard confirms it on its own. Questions go to
      <a href="mailto:${process.env.EMAIL_REPLY_TO || "baskinltd@yahoo.com"}" style="color:${B.accent};text-decoration:none">${process.env.EMAIL_REPLY_TO || "baskinltd@yahoo.com"}</a>.
    </div>
  </td></tr>
</table></td></tr></table></body></html>`;
}
