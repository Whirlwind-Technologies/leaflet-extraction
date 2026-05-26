"use client";

import { useEffect, useRef, useCallback, useSyncExternalStore } from "react";
import { getExportStatus } from "@/lib/actions/products";
import type { ExportStatusResponse, ExportJobStatus } from "@/lib/types";

interface UseExportPollResult {
  status: ExportJobStatus | null;
  data: ExportStatusResponse | null;
  downloadUrl: string | null;
  error: string | null;
  isPolling: boolean;
}

interface PollState {
  status: ExportJobStatus | null;
  data: ExportStatusResponse | null;
  downloadUrl: string | null;
  error: string | null;
  isPolling: boolean;
}

const POLL_INTERVAL_MS = 3000;

const IDLE_STATE: PollState = {
  status: null,
  data: null,
  downloadUrl: null,
  error: null,
  isPolling: false,
};

/**
 * Polls the export status endpoint every 3 seconds until the job
 * reaches "completed" or "failed". Cleans up on unmount.
 *
 * Pass `null` to stop polling.
 */
export function useExportPoll(exportId: string | null): UseExportPollResult {
  // Use a ref-based store to avoid setState-in-effect issues.
  const stateRef = useRef<PollState>({ ...IDLE_STATE });
  const listenersRef = useRef(new Set<() => void>());
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const mountedRef = useRef(true);

  const subscribe = useCallback((listener: () => void) => {
    listenersRef.current.add(listener);
    return () => { listenersRef.current.delete(listener); };
  }, []);

  const getSnapshot = useCallback(() => stateRef.current, []);

  const notify = useCallback(() => {
    listenersRef.current.forEach(l => l());
  }, []);

  const updateState = useCallback((patch: Partial<PollState>) => {
    stateRef.current = { ...stateRef.current, ...patch };
    notify();
  }, [notify]);

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    updateState({ isPolling: false });
  }, [updateState]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (!exportId) {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      stateRef.current = { ...IDLE_STATE };
      notify();
      return;
    }

    // Reset state for new export
    stateRef.current = {
      status: "pending",
      data: null,
      downloadUrl: null,
      error: null,
      isPolling: true,
    };
    notify();

    const poll = async () => {
      const result = await getExportStatus(exportId);

      if (!mountedRef.current) return;

      if (!result.success || !result.data) {
        updateState({ error: result.error || "Failed to check export status" });
        stopPolling();
        return;
      }

      const statusData = result.data;
      updateState({ status: statusData.status, data: statusData });

      if (statusData.status === "completed") {
        updateState({ downloadUrl: statusData.download_url || null });
        stopPolling();
      } else if (statusData.status === "failed") {
        updateState({ error: statusData.error_message || "Export failed" });
        stopPolling();
      }
    };

    // Poll immediately, then on interval
    poll();
    intervalRef.current = setInterval(poll, POLL_INTERVAL_MS);

    return () => {
      stopPolling();
    };
  }, [exportId, stopPolling, notify, updateState]);

  const state = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);

  return state;
}
