import { Suspense } from "react";
import { getRetailers } from "@/lib/actions/retailers";
import { RetailerRegistry } from "@/components/retailers/retailer-registry";
import { Card, CardContent } from "@/components/ui/card";

export const metadata = {
  title: "Retailer Registry | LeafXtract",
  description: "Manage retailers and their default metadata settings",
};

export default async function RetailersPage() {
  return (
    <div className="container mx-auto pb-6 max-w-7xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold mb-1 tracking-tight text-slate-800">
            Retailer Registry
          </h1>
          <p className="text-sm font-light text-slate-500">
            Manage retailers and their default metadata settings for leaflet uploads
          </p>
        </div>
      </div>

      <Suspense fallback={<RetailersSkeleton />}>
        <RetailersWrapper />
      </Suspense>
    </div>
  );
}

async function RetailersWrapper() {
  const retailers = await getRetailers();
  return <RetailerRegistry initialRetailers={retailers} />;
}

function RetailersSkeleton() {
  return (
    <Card className="border-slate-200">
      <CardContent className="p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-10 bg-slate-200 rounded w-1/3" />
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-16 bg-slate-100 rounded" />
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
