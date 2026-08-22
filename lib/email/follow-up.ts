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

export type Step = "nudge" | "proof" | "objection" | "last";

export type FollowUpInput = {
  step: Step;
  name: string;
  business: string;
  siteUrl: string;
  contactEmail: string;
};

/**
 * The three emails after the proposal, and the one that closes the file.
 *
 * Each carries something the last one did not. "Just checking in" is not a
 * reason to write to somebody, and they can tell.
 */
const COPY: Record<Step, { head: string; body: string[]; cta: string; ps?: string }> = {
  nudge: {
    head: "Your agent is built and sitting there.",
    body: [
      "I set it up from what you sent and it has been ready since. Nothing is running on your site yet, because that is your call, not mine.",
      "Turning it on takes one line of code and about a minute. If pasting code is the awkward part, send me the login and I will do it.",
    ],
    cta: "Turn it on",
  },
  proof: {
    head: "What it caught for somebody else last week.",
    body: [
      "A clinic switched theirs on a fortnight ago. In the first week the agent answered 34 messages. Nine of them arrived after closing, and four became appointments that nobody would have seen until the next morning.",
      "None of that needed a person. The owner read the conversations the next day and changed two lines in the description. That is the whole job.",
      "Yours would do the same on your own prices and your own hours.",
    ],
    cta: "Try it for two weeks",
    ps: "The numbers above are from one workspace, not an average. Yours will be different, which is why the trial exists.",
  },
  objection: {
    head: "The three things people ask before saying yes.",
    body: [
      "<b>What if it tells my customer something wrong?</b> It answers only from your description. No price in there, no price out — it says it does not know and takes a contact instead.",
      "<b>Where does my customers' data go?</b> Into your workspace and nowhere else. Not sold, not used for advertising, exportable and deletable whenever you want.",
      "<b>What if I want out?</b> Delete one line from your site and cancel. No notice, no call to talk you round.",
    ],
    cta: "Start the free two weeks",
  },
  last: {
    head: "Closing this off.",
    body: [
      "This is the last email — I would rather stop than become the thing you archive without reading.",
      "Your agent stays built. If it ever becomes useful, one reply and it is running the same day. No hard feelings either way, and good luck with the business.",
    ],
    cta: "Change your mind here",
  },
};

export function followUpEmail(input: FollowUpInput) {
  const copy = COPY[input.step];
  const host = input.siteUrl.replace(/^https?:\/\//, "");

  return `<!doctype html>
<html><body style="margin:0;padding:0;background:${BRAND.bg}">
<table width="100%" cellpadding="0" cellspacing="0" style="background:${BRAND.bg};padding:28px 12px">
<tr><td align="center">
<table width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%">

  <tr><td style="padding:8px 28px 22px">
    <span style="display:inline-block;background:${BRAND.accent};color:${BRAND.ink};border-radius:9px;padding:7px 10px;font:800 12px Helvetica,Arial,sans-serif">AI</span>
    <span style="font:700 17px Helvetica,Arial,sans-serif;color:${BRAND.text};margin-left:8px">AI FLOW</span>
  </td></tr>

  <tr><td style="padding:0 28px 18px">
    <div style="font:700 25px/1.2 Helvetica,Arial,sans-serif;color:${BRAND.text};letter-spacing:-.4px">
      ${input.name ? `${input.name}, ` : ""}${copy.head.charAt(0).toLowerCase()}${copy.head.slice(1)}
    </div>
  </td></tr>

  ${copy.body
    .map(
      (line) => `<tr><td style="padding:0 28px 14px">
        <div style="font:400 15px/1.65 Helvetica,Arial,sans-serif;color:${BRAND.muted}">${line}</div>
      </td></tr>`,
    )
    .join("")}

  <tr><td style="padding:14px 28px 8px">
    <a href="${input.siteUrl}#demo" style="display:inline-block;background:${BRAND.accent};color:${BRAND.ink};border-radius:999px;padding:13px 24px;font:700 15px Helvetica,Arial,sans-serif;text-decoration:none">${copy.cta}</a>
  </td></tr>

  ${
    copy.ps
      ? `<tr><td style="padding:18px 28px 0">
          <div style="font:400 13px/1.6 Helvetica,Arial,sans-serif;color:${BRAND.muted};padding:12px 15px;background:${BRAND.surface};border-left:2px solid ${BRAND.accent2};border-radius:0 8px 8px 0">${copy.ps}</div>
        </td></tr>`
      : ""
  }

  <tr><td style="padding:26px 28px 30px">
    <div style="border-top:1px solid ${BRAND.line};padding-top:18px;font:400 13px/1.7 Helvetica,Arial,sans-serif;color:${BRAND.muted}">
      Reply to this and a person reads it, not a robot.<br>
      <a href="mailto:${input.contactEmail}" style="color:${BRAND.accent2};text-decoration:none">${input.contactEmail}</a>
      &nbsp;·&nbsp;
      <a href="${input.siteUrl}" style="color:${BRAND.accent2};text-decoration:none">${host}</a>
    </div>
    <div style="font:400 11px/1.6 Helvetica,Arial,sans-serif;color:${BRAND.muted};margin-top:14px">
      You asked for a demo at ${host}. Reply with the word stop and this ends immediately.
    </div>
  </td></tr>

</table>
</td></tr></table>
</body></html>`;
}
