import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const API_BASE_URL = process.env.BACKEND_URL || "http://localhost:8000";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ leafletId: string }> }
) {
  try {
    const { leafletId } = await params;
    const cookieStore = await cookies();
    const token = cookieStore.get("access_token")?.value;

    if (!token) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    // Get query parameters
    const searchParams = request.nextUrl.searchParams;
    const format = searchParams.get("format") || "json";
    const imageStorage = searchParams.get("image_storage") || "url";
    const includeProductCodes = searchParams.get("include_product_codes") || "true";

    // Build URL with query params
    const queryParams = new URLSearchParams({
      format,
      image_storage: imageStorage,
      include_product_codes: includeProductCodes,
    });

    const backendUrl = `${API_BASE_URL}/api/v1/export/${leafletId}?${queryParams.toString()}`;

    const response = await fetch(backendUrl, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return NextResponse.json(
        { error: errorData.detail || "Export failed" },
        { status: response.status }
      );
    }

    // For CSV, return as file download
    if (format === "csv") {
      const csvData = await response.text();
      const contentDisposition = response.headers.get("Content-Disposition");
      
      return new NextResponse(csvData, {
        status: 200,
        headers: {
          "Content-Type": "text/csv",
          "Content-Disposition": contentDisposition || `attachment; filename="${leafletId}_export.csv"`,
        },
      });
    }

    // For JSON, return the data
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Export proxy error:", error);
    return NextResponse.json(
      { error: "An error occurred during export" },
      { status: 500 }
    );
  }
}