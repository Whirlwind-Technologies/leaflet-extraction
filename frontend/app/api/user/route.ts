import { NextResponse } from "next/server";
import { cookies } from "next/headers";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

export async function GET() {
  try {
    const cookieStore = await cookies();
    const token = cookieStore.get("access_token")?.value;

    if (!token) {
      return NextResponse.json(
        { error: "Unauthorized" },
        { status: 401 }
      );
    }

    // Fetch leaflets to calculate stats
    const leafletsResponse = await fetch(`${BACKEND_URL}/api/v1/leaflets?page_size=1000`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (!leafletsResponse.ok) {
      throw new Error("Failed to fetch leaflets");
    }

    const leafletsData = await leafletsResponse.json();
    const leaflets = leafletsData.items || [];

    // Calculate stats
    const totalLeaflets = leafletsData.total || leaflets.length;
    const completedLeaflets = leaflets.filter(
      (l: { status: string }) => l.status === "completed"
    ).length;

    // Sum up products from all leaflets
    const totalProducts = leaflets.reduce(
      (sum: number, l: { products_count?: number }) => sum + (l.products_count || 0),
      0
    );

    // Sum up pending reviews
    const pendingReviews = leaflets.reduce(
      (sum: number, l: { review_required_count?: number }) => sum + (l.review_required_count || 0),
      0
    );

    return NextResponse.json({
      total_leaflets: totalLeaflets,
      total_products: totalProducts,
      completed_leaflets: completedLeaflets,
      pending_reviews: pendingReviews,
    });
  } catch (error) {
    console.error("Error fetching user stats:", error);
    return NextResponse.json(
      {
        total_leaflets: 0,
        total_products: 0,
        completed_leaflets: 0,
        pending_reviews: 0,
      },
      { status: 200 }
    );
  }
}