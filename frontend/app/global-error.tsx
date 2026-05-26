"use client";

import { useEffect } from "react";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Log the error to an error reporting service
    console.error("Global error:", error);
  }, [error]);

  return (
    <html>
      <body>
        <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
          <div className="max-w-md w-full bg-white rounded-lg shadow-lg p-8 text-center">
            <div className="flex justify-center mb-6">
              <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center">
                <AlertTriangle className="h-8 w-8 text-red-600" strokeWidth={1.5} />
              </div>
            </div>

            <h1 className="text-2xl font-light text-[#2D3748] mb-2 tracking-tight">
              Something Went <span className="font-normal">Wrong</span>
            </h1>

            <p className="text-sm text-[#6B7280] mb-6">
              An unexpected error occurred. Our team has been notified and we&apos;re working on a fix.
            </p>

            {error.digest && (
              <p className="text-xs text-[#9CA3AF] mb-6 font-mono bg-gray-100 p-2 rounded">
                Error ID: {error.digest}
              </p>
            )}

            <div className="flex flex-col sm:flex-row gap-3 justify-center">
              <Button
                onClick={() => reset()}
                className="bg-[#5B8DBE] hover:bg-[#4A7BA7] text-white"
              >
                Try Again
              </Button>
              <Button
                onClick={() => window.location.href = "/dashboard"}
                variant="outline"
                className="border-[#5B8DBE] text-[#5B8DBE] hover:bg-[#5B8DBE]/10"
              >
                Go to Dashboard
              </Button>
            </div>

            {process.env.NODE_ENV === "development" && (
              <details className="mt-6 text-left">
                <summary className="cursor-pointer text-sm text-[#6B7280] hover:text-[#2D3748]">
                  Error Details (Development Only)
                </summary>
                <pre className="mt-2 text-xs bg-gray-100 p-3 rounded overflow-auto max-h-40">
                  {error.message}
                  {"\n\n"}
                  {error.stack}
                </pre>
              </details>
            )}
          </div>
        </div>
      </body>
    </html>
  );
}
