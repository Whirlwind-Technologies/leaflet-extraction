import { Loader2 } from "lucide-react";

export default function Loading() {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="text-center">
        <Loader2 className="h-12 w-12 text-[#5B8DBE] animate-spin mx-auto mb-4" strokeWidth={1.5} />
        <p className="text-sm font-light text-[#6B7280]">
          Loading...
        </p>
      </div>
    </div>
  );
}
