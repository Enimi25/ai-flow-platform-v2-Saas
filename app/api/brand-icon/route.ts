import { NextResponse } from "next/server";
import { promises as fs } from "node:fs";
import path from "node:path";

/** The app icon, served with an open origin so it can be attached from a portal form. */
export async function GET() {
  const file = await fs.readFile(path.join(process.cwd(), "public", "ai-flow-icon.png"));
  return new NextResponse(new Uint8Array(file), {
    headers: {
      "Content-Type": "image/png",
      "Access-Control-Allow-Origin": "*",
      "Cache-Control": "no-store",
    },
  });
}
