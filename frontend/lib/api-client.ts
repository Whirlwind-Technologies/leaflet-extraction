import { cookies } from "next/headers";

const API_BASE_URL = process.env.BACKEND_URL || "http://localhost:8000";

/**
 * Pull a human-readable error message out of a backend error response.
 *
 * The backend wraps custom errors in `{ error: { code, message, details } }`
 * (see `backend/app/main.py`), while FastAPI's built-in validation errors
 * still use the `{ detail: ... }` shape. We prefer the structured
 * envelope when present and fall back to `detail` so we surface the
 * actual cause rather than a generic "HTTP error!" message.
 */
function extractErrorMessage(payload: unknown, status: number): string {
  if (payload && typeof payload === "object") {
    const data = payload as Record<string, unknown>;

    // Custom backend envelope
    const wrapped = data.error;
    if (wrapped && typeof wrapped === "object") {
      const msg = (wrapped as Record<string, unknown>).message;
      if (typeof msg === "string" && msg.length > 0) {
        return msg;
      }
    }

    // FastAPI default validation envelope: detail can be string OR list
    const detail = data.detail;
    if (typeof detail === "string" && detail.length > 0) {
      return detail;
    }
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0] as Record<string, unknown>;
      if (typeof first?.msg === "string") return first.msg as string;
    }
  }

  return `HTTP error! status: ${status}`;
}

export async function getAuthToken(): Promise<string | null> {
  const cookieStore = await cookies();
  return cookieStore.get("access_token")?.value || null;
}

export async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = await getAuthToken();

  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...options.headers,
  };

  if (token) {
    (headers as Record<string, string>)["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
    cache: "no-store",
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(extractErrorMessage(errorData, response.status));
  }

  return response.json();
}

export async function apiRequestWithFormData<T>(
  endpoint: string,
  formData: FormData
): Promise<T> {
  const token = await getAuthToken();

  const headers: HeadersInit = {};

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    method: "POST",
    headers,
    body: formData,
    cache: "no-store",
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(extractErrorMessage(errorData, response.status));
  }

  return response.json();
}