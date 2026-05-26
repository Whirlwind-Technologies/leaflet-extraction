import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";

const API_BASE_URL = process.env.BACKEND_URL || "http://localhost:8000";

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string; action: string }> }
) {
  try {
    const { id, action } = await params;
    const cookieStore = await cookies();
    const token = cookieStore.get("access_token")?.value;

    if (!token) {
      return NextResponse.json(
        { error: { message: "Unauthorized" } },
        { status: 401 }
      );
    }

    if (action !== "approve" && action !== "reject" && action !== "suspend") {
      return NextResponse.json(
        { error: { message: "Invalid action" } },
        { status: 400 }
      );
    }

    // Get request body if present
    const body = await request.text();

    const response = await fetch(
      `${API_BASE_URL}/api/v1/admin/registrations/${id}/${action}`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        ...(body && { body }),
      }
    );

    if (!response.ok) {
      const error = await response.json();
      return NextResponse.json(error, { status: response.status });
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Error processing registration action:", error);
    return NextResponse.json(
      { error: { message: "Failed to process action" } },
      { status: 500 }
    );
  }
}
