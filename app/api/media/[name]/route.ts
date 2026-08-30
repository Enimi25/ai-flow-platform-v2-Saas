import { promises as fs } from "node:fs";
import { createReadStream } from "node:fs";
import path from "node:path";
import { Readable } from "node:stream";
import { NextResponse } from "next/server";
import { MEDIA_DIR } from "@/lib/content/video";

/**
 * Serves rendered reels to whoever publishes them.
 *
 * Meta and TikTok fetch the video from a public URL rather than accepting an
 * upload from us, so the file has to be reachable here. Range requests are
 * honoured because both platforms probe with them before pulling the file.
 */

const NAME = /^[a-z0-9-]{1,64}\.mp4$/i;

export async function GET(request: Request, context: { params: Promise<{ name: string }> }) {
  const { name } = await context.params;
  if (!NAME.test(name)) return new NextResponse("Not found", { status: 404 });

  const file = path.join(MEDIA_DIR(), name);
  let size: number;
  try {
    size = (await fs.stat(file)).size;
  } catch {
    return new NextResponse("Not found", { status: 404 });
  }

  const common = {
    "Content-Type": "video/mp4",
    "Accept-Ranges": "bytes",
    "Cache-Control": "public, max-age=86400",
  };

  const range = request.headers.get("range");
  const match = range?.match(/bytes=(\d*)-(\d*)/);
  if (match && (match[1] || match[2])) {
    const start = match[1] ? parseInt(match[1], 10) : Math.max(0, size - parseInt(match[2], 10));
    const end = match[1] && match[2] ? Math.min(parseInt(match[2], 10), size - 1) : size - 1;
    if (Number.isNaN(start) || start >= size || start > end) {
      return new NextResponse(null, { status: 416, headers: { "Content-Range": `bytes */${size}` } });
    }
    const stream = Readable.toWeb(createReadStream(file, { start, end })) as ReadableStream;
    return new NextResponse(stream, {
      status: 206,
      headers: {
        ...common,
        "Content-Range": `bytes ${start}-${end}/${size}`,
        "Content-Length": String(end - start + 1),
      },
    });
  }

  const stream = Readable.toWeb(createReadStream(file)) as ReadableStream;
  return new NextResponse(stream, { status: 200, headers: { ...common, "Content-Length": String(size) } });
}
