import { grantFor, refreshAccessToken } from "./oauth";

const CAL = "https://www.googleapis.com/calendar/v3";

export type Appointment = {
  summary: string;
  description?: string;
  startsAt: string;
  endsAt: string;
  attendeeEmail?: string;
  timeZone?: string;
};

/**
 * Writes straight into the owner's calendar using the refresh token captured
 * at sign in, so a booking needs no further interaction from them.
 */
export async function createEvent(ownerEmail: string, appointment: Appointment) {
  const grant = await grantFor(ownerEmail);
  if (!grant) throw new Error(`${ownerEmail} has not connected a Google calendar.`);

  const { access_token } = await refreshAccessToken(grant.refreshToken);

  const target = encodeURIComponent(grant.calendarId || "primary");
  const response = await fetch(
    `${CAL}/calendars/${target}/events?sendUpdates=all`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${access_token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        summary: appointment.summary,
        description: appointment.description,
        start: { dateTime: appointment.startsAt, timeZone: appointment.timeZone ?? "UTC" },
        end: { dateTime: appointment.endsAt, timeZone: appointment.timeZone ?? "UTC" },
        attendees: appointment.attendeeEmail ? [{ email: appointment.attendeeEmail }] : undefined,
      }),
    },
  );

  const payload = await response.json();
  if (!response.ok) throw new Error(payload?.error?.message ?? "Google Calendar rejected the event.");
  return payload as { id: string; htmlLink: string };
}

export type CalendarChoice = { id: string; summary: string; primary?: boolean; accessRole: string };

/** The calendars this account can write to, for the confirmation screen. */
export async function listCalendars(ownerEmail: string) {
  const grant = await grantFor(ownerEmail);
  if (!grant) throw new Error("No Google account connected.");

  const { access_token } = await refreshAccessToken(grant.refreshToken);
  const response = await fetch(`${CAL}/users/me/calendarList?minAccessRole=writer`, {
    headers: { Authorization: `Bearer ${access_token}` },
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload?.error?.message ?? "Google would not list the calendars.");

  return {
    chosen: grant.calendarId ?? null,
    calendars: (payload.items as CalendarChoice[]).map((item) => ({
      id: item.id,
      summary: item.summary,
      primary: item.primary,
      accessRole: item.accessRole,
    })),
  };
}
