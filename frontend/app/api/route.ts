import { NextRequest, NextResponse } from "next/server";

// This file already exists in the repo at app/api/v1/[...path]/route.ts.
// It forwards every /api/v1/* request to the FastAPI backend during local development.
// In production, NEXT_PUBLIC_BACKEND_URL is set so the browser calls the backend directly —
// this proxy is never invoked.

const BACKEND_URL =
  process.env.BACKEND_URL ?? process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

export async function GET(req: NextRequest, { params }: { params: { path: string[] } }) {
  return proxy(req, params.path);
}

export async function POST(req: NextRequest, { params }: { params: { path: string[] } }) {
  return proxy(req, params.path);
}

export async function DELETE(req: NextRequest, { params }: { params: { path: string[] } }) {
  return proxy(req, params.path);
}

export async function PUT(req: NextRequest, { params }: { params: { path: string[] } }) {
  return proxy(req, params.path);
}

async function proxy(req: NextRequest, pathSegments: string[]) {
  const path = pathSegments.join("/");
  const url = `${BACKEND_URL}/api/v1/${path}${req.nextUrl.search}`;

  const body = req.method !== "GET" && req.method !== "DELETE"
    ? await req.text()
    : undefined;

  const res = await fetch(url, {
    method: req.method,
    headers: {
      "Content-Type": "application/json",
      ...Object.fromEntries(req.headers),
    },
    body,
  });

  const data = res.status === 204 ? null : await res.text();
  return new NextResponse(data, {
    status: res.status,
    headers: { "Content-Type": "application/json" },
  });
}
