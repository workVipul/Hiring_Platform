import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";

async function proxy(req: NextRequest, pathSegments: string[]) {
  const url = `${BACKEND}/api/v1/${pathSegments.join("/")}${req.nextUrl.search}`;
  const body = req.method !== "GET" && req.method !== "DELETE" ? await req.text() : undefined;
  const res = await fetch(url, {
    method: req.method,
    headers: { "Content-Type": "application/json" },
    body,
  });
  const data = res.status === 204 ? null : await res.text();
  return new NextResponse(data, {
    status: res.status,
    headers: { "Content-Type": "application/json" },
  });
}

export async function GET(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  return proxy(req, (await params).path);
}
export async function POST(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  return proxy(req, (await params).path);
}
export async function DELETE(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  return proxy(req, (await params).path);
}
export async function PUT(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  return proxy(req, (await params).path);
}