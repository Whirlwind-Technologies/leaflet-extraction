"use client";

import { useEffect, useState, useCallback } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import { AlertTriangle, Settings, X, CheckCircle, Info } from "lucide-react";
import { getVlmStatus, VlmStatus } from "@/lib/actions/settings";

// Custom event name for VLM status changes
export const VLM_STATUS_CHANGED_EVENT = "vlm-status-changed";

// Custom event name for platform quota changes (e.g. after extraction blocked by limit)
export const PLATFORM_QUOTA_CHANGED_EVENT = "platform-quota-changed";

// Helper function to dispatch the event (call this after creating/deleting providers)
export function dispatchVlmStatusChanged() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(VLM_STATUS_CHANGED_EVENT));
  }
}

/**
 * Dispatch when platform quota is known to have changed — for example when
 * an extraction is blocked by the platform limit. Any component displaying
 * quota information should listen for this event and refetch.
 */
export function dispatchPlatformQuotaChanged() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(PLATFORM_QUOTA_CHANGED_EVENT));
  }
}

interface VlmStatusBannerProps {
  /** Allow user to dismiss the banner */
  dismissible?: boolean;
  /** Compact mode for smaller spaces */
  compact?: boolean;
  /** Show even when provider is configured (for info) */
  showWhenConfigured?: boolean;
}

export function VlmStatusBanner({
  dismissible = true,
  compact = false,
  showWhenConfigured = false,
}: VlmStatusBannerProps) {
  const [status, setStatus] = useState<VlmStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [dismissed, setDismissed] = useState(false);
  const pathname = usePathname();

  const fetchStatus = useCallback(async () => {
    try {
      setLoading(true);
      const vlmStatus = await getVlmStatus();
      setStatus(vlmStatus);
      // Reset dismissed state if provider status changed
      if (vlmStatus.can_extract) {
        setDismissed(false);
      }
    } catch (error) {
      console.error("Failed to fetch VLM status:", error);
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch on mount
  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  // Refetch when pathname changes (user navigates)
  useEffect(() => {
    fetchStatus();
  }, [pathname, fetchStatus]);

  // Refetch when tab becomes visible again
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        fetchStatus();
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [fetchStatus]);

  // Listen for custom VLM status changed events
  useEffect(() => {
    const handleVlmStatusChanged = () => {
      fetchStatus();
    };

    window.addEventListener(VLM_STATUS_CHANGED_EVENT, handleVlmStatusChanged);
    return () => {
      window.removeEventListener(VLM_STATUS_CHANGED_EVENT, handleVlmStatusChanged);
    };
  }, [fetchStatus]);

  // Don't show anything while loading
  if (loading) {
    return null;
  }

  // Don't show if dismissed
  if (dismissed) {
    return null;
  }

  // Don't show if user has their own active provider configured (unless showWhenConfigured is true)
  if (status?.has_active_provider && !showWhenConfigured) {
    return null;
  }

  // No provider and no fallback - Critical warning
  if (!status?.can_extract) {
    return (
      <div className={`relative rounded-lg border border-amber-200 bg-amber-50 dark:border-amber-900/50 dark:bg-amber-950/30 ${compact ? 'p-3' : 'p-4'}`}>
        {dismissible && (
          <button
            onClick={() => setDismissed(true)}
            className="absolute right-2 top-2 p-1 rounded-md hover:bg-amber-100 dark:hover:bg-amber-900/50 text-amber-600 dark:text-amber-400"
          >
            <X className="h-4 w-4" />
          </button>
        )}

        <div className="flex items-start gap-3">
          <div className="flex-shrink-0">
            <AlertTriangle className={`${compact ? 'h-5 w-5' : 'h-6 w-6'} text-amber-500`} />
          </div>

          <div className="flex-1 min-w-0">
            <h3 className={`font-semibold text-amber-800 dark:text-amber-200 ${compact ? 'text-sm' : 'text-base'}`}>
              AI Provider Not Configured
            </h3>

            {!compact && (
              <p className="mt-1 text-sm text-amber-700 dark:text-amber-300">
                No AI provider is available for extraction. You can configure your own API key in Settings,
                or contact your administrator to set up platform-level providers.
              </p>
            )}

            <div className={`${compact ? 'mt-2' : 'mt-3'} flex flex-wrap gap-2`}>
              <Link
                href="/settings?tab=ai-providers"
                className={`inline-flex items-center gap-1.5 rounded-md bg-amber-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-amber-700 transition-colors ${compact ? 'text-xs px-2 py-1' : ''}`}
              >
                <Settings className="h-4 w-4" />
                Configure AI Provider
              </Link>

              {!compact && (
                <Link
                  href="/docs/getting-started"
                  className="inline-flex items-center gap-1.5 rounded-md border border-amber-300 dark:border-amber-700 bg-white dark:bg-amber-950 px-3 py-1.5 text-sm font-medium text-amber-700 dark:text-amber-300 hover:bg-amber-50 dark:hover:bg-amber-900 transition-colors"
                >
                  Learn More
                </Link>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Using platform provider - Info notice
  if (status?.can_extract && !status?.has_active_provider && status?.has_fallback) {
    return (
      <div className={`relative rounded-lg border border-blue-200 bg-blue-50 dark:border-blue-900/50 dark:bg-blue-950/30 ${compact ? 'p-3' : 'p-4'}`}>
        {dismissible && (
          <button
            onClick={() => setDismissed(true)}
            className="absolute right-2 top-2 p-1 rounded-md hover:bg-blue-100 dark:hover:bg-blue-900/50 text-blue-600 dark:text-blue-400"
          >
            <X className="h-4 w-4" />
          </button>
        )}

        <div className="flex items-start gap-3">
          <div className="flex-shrink-0">
            <Info className={`${compact ? 'h-5 w-5' : 'h-6 w-6'} text-blue-500`} />
          </div>

          <div className="flex-1 min-w-0">
            <h3 className={`font-semibold text-blue-800 dark:text-blue-200 ${compact ? 'text-sm' : 'text-base'}`}>
              Using Platform AI Provider
            </h3>

            {!compact && (
              <p className="mt-1 text-sm text-blue-700 dark:text-blue-300">
                Extraction is enabled using the platform&apos;s shared AI provider managed by your administrator.
                For dedicated usage and budget control, you can configure your own API key.
              </p>
            )}

            <div className={`${compact ? 'mt-2' : 'mt-3'}`}>
              <Link
                href="/settings?tab=ai-providers"
                className={`inline-flex items-center gap-1.5 text-sm font-medium text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-200 transition-colors ${compact ? 'text-xs' : ''}`}
              >
                <Settings className="h-4 w-4" />
                Add Your Own API Key
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Provider configured - Success notice (only shown if showWhenConfigured)
  if (status?.has_active_provider && showWhenConfigured) {
    return (
      <div className={`relative rounded-lg border border-green-200 bg-green-50 dark:border-green-900/50 dark:bg-green-950/30 ${compact ? 'p-3' : 'p-4'}`}>
        {dismissible && (
          <button
            onClick={() => setDismissed(true)}
            className="absolute right-2 top-2 p-1 rounded-md hover:bg-green-100 dark:hover:bg-green-900/50 text-green-600 dark:text-green-400"
          >
            <X className="h-4 w-4" />
          </button>
        )}
        
        <div className="flex items-start gap-3">
          <div className="flex-shrink-0">
            <CheckCircle className={`${compact ? 'h-5 w-5' : 'h-6 w-6'} text-green-500`} />
          </div>
          
          <div className="flex-1 min-w-0">
            <h3 className={`font-semibold text-green-800 dark:text-green-200 ${compact ? 'text-sm' : 'text-base'}`}>
              AI Provider Ready
            </h3>
            
            {!compact && (
              <p className="mt-1 text-sm text-green-700 dark:text-green-300">
                Using <span className="font-medium">{status.default_provider}</span> for product extraction.
                {status.active_count > 1 && ` (${status.active_count} providers configured)`}
              </p>
            )}
          </div>
        </div>
      </div>
    );
  }

  return null;
}

// Hook for components that need VLM status
export function useVlmStatus() {
  const [status, setStatus] = useState<VlmStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const pathname = usePathname();

  const fetchStatus = useCallback(async () => {
    try {
      setLoading(true);
      const vlmStatus = await getVlmStatus();
      setStatus(vlmStatus);
      setError(null);
    } catch (err) {
      setError("Failed to fetch VLM status");
      console.error("Failed to fetch VLM status:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch on mount and pathname change
  useEffect(() => {
    fetchStatus();
  }, [pathname, fetchStatus]);

  const refetch = async () => {
    setLoading(true);
    try {
      const vlmStatus = await getVlmStatus();
      setStatus(vlmStatus);
      setError(null);
    } catch {
      setError("Failed to fetch VLM status");
    } finally {
      setLoading(false);
    }
  };

  return { status, loading, error, refetch };
}