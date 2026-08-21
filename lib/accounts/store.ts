import { promises as fs } from "node:fs";
import path from "node:path";
import { randomBytes, scrypt as scryptCallback, timingSafeEqual } from "node:crypto";
import { promisify } from "node:util";
import { withFileLock, readJson, writeJson } from "@/lib/json-store";

const scrypt = promisify(scryptCallback) as (
  password: string,
  salt: Buffer,
  keylen: number,
) => Promise<Buffer>;

export type Account = {
  email: string;
  /** scrypt, stored as salt:hash in hex. Never the password itself. */
  secret: string;
  role: string;
  createdAt: string;
};

const FILE = path.join(process.cwd(), ".data", "accounts.json");
const readAll = () => readJson<Account[]>(FILE, []);

/**
 * scrypt with a per-account salt. Slow on purpose: if the accounts file ever
 * leaks, a stolen hash should be worth nothing without months of compute.
 */
async function hash(password: string) {
  const salt = randomBytes(16);
  const derived = await scrypt(password, salt, 64);
  return `${salt.toString("hex")}:${derived.toString("hex")}`;
}

async function matches(password: string, secret: string) {
  const [saltHex, hashHex] = secret.split(":");
  if (!saltHex || !hashHex) return false;
  const derived = await scrypt(password, Buffer.from(saltHex, "hex"), 64);
  const stored = Buffer.from(hashHex, "hex");
  return derived.length === stored.length && timingSafeEqual(derived, stored);
}

export async function accountExists(email: string) {
  return (await readAll()).some((account) => account.email === email.toLowerCase());
}

export async function createAccount(email: string, password: string) {
  const clean = email.trim().toLowerCase();
  return withFileLock(FILE, async () => {
    const all = await readAll();
    if (all.some((account) => account.email === clean)) return null;

    const account: Account = {
      email: clean,
      secret: await hash(password),
      // the first account to register owns the platform; everyone after is a customer
      role: all.length === 0 ? "admin" : "owner",
      createdAt: new Date().toISOString(),
    };
    await writeJson(FILE, [...all, account]);
    return account;
  });
}

/** The account, or null. Null covers both "no such email" and "wrong password". */
export async function verifyAccount(email: string, password: string) {
  const clean = email.trim().toLowerCase();
  const account = (await readAll()).find((item) => item.email === clean);
  if (!account) {
    // spend the same time as a real check so the response cannot be used to
    // work out which addresses have accounts
    await scrypt(password, randomBytes(16), 64);
    return null;
  }
  return (await matches(password, account.secret)) ? account : null;
}

export async function countAccounts() {
  return (await readAll()).length;
}
