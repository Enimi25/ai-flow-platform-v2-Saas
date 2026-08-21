import { createCipheriv, createDecipheriv, randomBytes, scryptSync } from "node:crypto";

/**
 * Refresh tokens are long lived keys to a customer's calendar. They are never
 * written to disk in the clear, and the process refuses to store one at all if
 * no encryption key is configured.
 */
function key() {
  const secret = process.env.TOKEN_ENCRYPTION_KEY;
  if (!secret || secret.length < 32) {
    throw new Error("TOKEN_ENCRYPTION_KEY must be at least 32 characters before tokens can be stored.");
  }
  return scryptSync(secret, "ai-flow-token", 32);
}

export function seal(plain: string) {
  const iv = randomBytes(12);
  const cipher = createCipheriv("aes-256-gcm", key(), iv);
  const body = Buffer.concat([cipher.update(plain, "utf8"), cipher.final()]);
  return [iv.toString("base64url"), cipher.getAuthTag().toString("base64url"), body.toString("base64url")].join(".");
}

export function open(sealed: string) {
  const [iv, tag, body] = sealed.split(".");
  if (!iv || !tag || !body) throw new Error("Stored token is malformed.");
  const decipher = createDecipheriv("aes-256-gcm", key(), Buffer.from(iv, "base64url"));
  decipher.setAuthTag(Buffer.from(tag, "base64url"));
  return Buffer.concat([decipher.update(Buffer.from(body, "base64url")), decipher.final()]).toString("utf8");
}
