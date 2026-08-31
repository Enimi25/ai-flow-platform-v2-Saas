/**
 * Absolute URL on the site the visitor is actually on.
 *
 * Behind Railway's proxy request.url says localhost:8080, so every redirect
 * built from it sent people to a server that only exists inside the container.
 * That is exactly what a Google sign-in did: consent on aiflow.forum, then a
 * redirect to localhost:8080/calendar/confirm and a dead fox page.
 */
export function publicUrl(path: string, request: Request): URL {
  const configured = process.env.PUBLIC_SITE_URL;
  if (configured) return new URL(path, configured);

  const forwardedHost = (request.headers.get("x-forwarded-host") ?? "").split(",")[0].trim();
  if (forwardedHost) {
    const proto = (request.headers.get("x-forwarded-proto") ?? "https").split(",")[0].trim();
    return new URL(path, `${proto}://${forwardedHost}`);
  }
  return new URL(path, new URL(request.url).origin);
}
