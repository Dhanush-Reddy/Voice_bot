import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL;

async function proxyRequest(request: NextRequest, { params }: { params: { path: string[] } }) {
    if (!BACKEND_URL) {
        return NextResponse.json({ error: "Backend URL not configured" }, { status: 500 });
    }

    const session = await getServerSession(authOptions);
    if (!session || !session.user || !(session.user as any).id) {
        return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const pathString = params.path.join("/");
    const searchParams = request.nextUrl.search;
    const targetUrl = `${BACKEND_URL}/api/${pathString}${searchParams}`;

    const headers = new Headers(request.headers);
    // Explicitly add our secure internal user ID header
    headers.set("x-user-id", (session.user as any).id);
    // Remove host header to avoid SSL/Routing mismatches when proxying
    headers.delete("host");
    headers.delete("connection");

    try {
        const fetchOptions: RequestInit = {
            method: request.method,
            headers,
            redirect: "manual",
        };

        if (request.method !== "GET" && request.method !== "HEAD") {
            const body = await request.arrayBuffer();
            if (body.byteLength > 0) {
                fetchOptions.body = body;
            }
        }

        const backendResponse = await fetch(targetUrl, fetchOptions);

        const responseHeaders = new Headers(backendResponse.headers);
        responseHeaders.delete("content-encoding");

        return new NextResponse(backendResponse.body, {
            status: backendResponse.status,
            statusText: backendResponse.statusText,
            headers: responseHeaders,
        });
    } catch (error) {
        console.error("Proxy error:", error);
        return NextResponse.json({ error: "Backend communication failed" }, { status: 502 });
    }
}

export const GET = proxyRequest;
export const POST = proxyRequest;
export const PUT = proxyRequest;
export const PATCH = proxyRequest;
export const DELETE = proxyRequest;
