"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { z } from "zod";
import type { ActionResult, AuthResponse, User } from "@/lib/types";

const API_BASE_URL = process.env.BACKEND_URL || "http://localhost:8000";

const loginSchema = z.object({
  email: z.string().email("Invalid email address"),
  password: z.string().min(1, "Password is required"),
});

const registerSchema = z.object({
  email: z.string().email("Invalid email address"),
  password: z
    .string()
    .min(8, "Password must be at least 8 characters")
    .regex(/[A-Z]/, "Password must contain an uppercase letter")
    .regex(/[a-z]/, "Password must contain a lowercase letter")
    .regex(/[0-9]/, "Password must contain a number"),
  fullName: z.string().min(2, "Name must be at least 2 characters"),
});

export async function login(
  _prevState: ActionResult,
  formData: FormData
): Promise<ActionResult<{ user: User; pending?: boolean; organizationName?: string }>> {
  const rawData = {
    email: formData.get("email") as string,
    password: formData.get("password") as string,
  };

  const validatedData = loginSchema.safeParse(rawData);

  if (!validatedData.success) {
    const errors = validatedData.error.flatten();
    const firstError =
      errors.fieldErrors.email?.[0] ||
      errors.fieldErrors.password?.[0] ||
      "Validation failed";
    return {
      success: false,
      error: firstError,
    };
  }

  try {
    // Login to get token
    const authResponse = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(validatedData.data),
    });

    if (!authResponse.ok) {
      const errorData = await authResponse.json().catch(() => ({}));

      // Check if it's a 403 error (pending approval or suspended)
      if (authResponse.status === 403) {
        // Handle object detail
        if (typeof errorData.detail === 'object') {
          // Pending approval case
          if (errorData.detail.status === "pending_approval") {
            return {
              success: false,
              error: errorData.detail.message || "Your business registration is pending approval",
              data: {
                pending: true,
                organizationName: errorData.detail.organization_name,
              } as { user: User; pending?: boolean; organizationName?: string },
            };
          }
          // Suspended/rejected case
          if (errorData.detail.status === "suspended") {
            return {
              success: false,
              error: errorData.detail.message || "Your business account has been suspended",
              data: {
                pending: false,
                organizationName: errorData.detail.organization_name,
              } as { user: User; pending?: boolean; organizationName?: string },
            };
          }
        }
        // Handle string detail
        return {
          success: false,
          error: typeof errorData.detail === 'string' ? errorData.detail : "Access forbidden",
        };
      }

      // Handle other errors - ensure we always return a string
      const errorMessage = typeof errorData.detail === 'string'
        ? errorData.detail
        : errorData.detail?.message || errorData.message || "Invalid email or password";

      return {
        success: false,
        error: errorMessage,
      };
    }

    const authData: AuthResponse = await authResponse.json();

    // Set cookies for both access and refresh tokens
    const cookieStore = await cookies();
    cookieStore.set("access_token", authData.access_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      maxAge: 60 * 60 * 8, // 8 hours (matches backend token expiration)
      path: "/",
    });

    // Store refresh token for automatic renewal
    if (authData.refresh_token) {
      cookieStore.set("refresh_token", authData.refresh_token, {
        httpOnly: true,
        secure: process.env.NODE_ENV === "production",
        sameSite: "lax",
        maxAge: 60 * 60 * 24 * 30, // 30 days
        path: "/",
      });
    }

    // Get user data
    const userResponse = await fetch(`${API_BASE_URL}/api/v1/auth/me`, {
      headers: {
        Authorization: `Bearer ${authData.access_token}`,
      },
    });

    if (!userResponse.ok) {
      return {
        success: false,
        error: "Failed to get user data",
      };
    }

    const user: User = await userResponse.json();

    return {
      success: true,
      data: { user },
    };
  } catch (error) {
    console.error("Login error:", error);
    return {
      success: false,
      error: "An unexpected error occurred",
    };
  }
}

export async function register(
  _prevState: ActionResult,
  formData: FormData
): Promise<ActionResult<{ user: User; pending?: boolean }>> {
  const accountType = formData.get("accountType") as string;

  // Business registration
  if (accountType === "business") {
    const rawData = {
      email: formData.get("email") as string,
      password: formData.get("password") as string,
      fullName: formData.get("fullName") as string,
      organizationName: formData.get("organizationName") as string,
      businessEmail: formData.get("businessEmail") as string,
      businessPhone: formData.get("businessPhone") as string,
    };

    const validatedData = registerSchema.safeParse({
      email: rawData.email,
      password: rawData.password,
      fullName: rawData.fullName,
    });

    if (!validatedData.success) {
      const errors = validatedData.error.flatten();
      const firstError =
        errors.fieldErrors.email?.[0] ||
        errors.fieldErrors.password?.[0] ||
        errors.fieldErrors.fullName?.[0] ||
        "Validation failed";
      return {
        success: false,
        error: firstError,
      };
    }

    // Validate business fields
    if (!rawData.organizationName || rawData.organizationName.length < 2) {
      return {
        success: false,
        error: "Company name must be at least 2 characters",
      };
    }

    if (!rawData.businessEmail || !rawData.businessEmail.includes("@")) {
      return {
        success: false,
        error: "Valid business email is required",
      };
    }

    try {
      // Register business account
      const registerResponse = await fetch(`${API_BASE_URL}/api/v1/auth/register/business`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: validatedData.data.email,
          password: validatedData.data.password,
          full_name: validatedData.data.fullName,
          organization_name: rawData.organizationName,
          business_email: rawData.businessEmail,
          business_phone: rawData.businessPhone || null,
        }),
      });

      if (!registerResponse.ok) {
        const errorData = await registerResponse.json().catch(() => ({}));
        return {
          success: false,
          error: errorData.detail || errorData.error?.message || "Registration failed",
        };
      }

      const user: User = await registerResponse.json();

      // Return success with pending flag (user account is inactive until approved)
      return {
        success: true,
        data: { user, pending: true },
      };
    } catch (error) {
      console.error("Business registration error:", error);
      return {
        success: false,
        error: "An unexpected error occurred",
      };
    }
  }

  // Personal registration (fallback for backward compatibility)
  const rawData = {
    email: formData.get("email") as string,
    password: formData.get("password") as string,
    fullName: formData.get("fullName") as string,
  };

  const validatedData = registerSchema.safeParse(rawData);

  if (!validatedData.success) {
    const errors = validatedData.error.flatten();
    const firstError =
      errors.fieldErrors.email?.[0] ||
      errors.fieldErrors.password?.[0] ||
      errors.fieldErrors.fullName?.[0] ||
      "Validation failed";
    return {
      success: false,
      error: firstError,
    };
  }

  try {
    // Register user
    const registerResponse = await fetch(`${API_BASE_URL}/api/v1/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: validatedData.data.email,
        password: validatedData.data.password,
        full_name: validatedData.data.fullName,
      }),
    });

    if (!registerResponse.ok) {
      const errorData = await registerResponse.json().catch(() => ({}));
      return {
        success: false,
        error: errorData.detail || "Registration failed",
      };
    }

    // Login after registration
    const authResponse = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: validatedData.data.email,
        password: validatedData.data.password,
      }),
    });

    if (!authResponse.ok) {
      return {
        success: false,
        error: "Registration successful but login failed",
      };
    }

    const authData: AuthResponse = await authResponse.json();

    // Set cookies for both access and refresh tokens
    const cookieStore = await cookies();
    cookieStore.set("access_token", authData.access_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      maxAge: 60 * 60 * 8, // 8 hours
      path: "/",
    });

    if (authData.refresh_token) {
      cookieStore.set("refresh_token", authData.refresh_token, {
        httpOnly: true,
        secure: process.env.NODE_ENV === "production",
        sameSite: "lax",
        maxAge: 60 * 60 * 24 * 30, // 30 days
        path: "/",
      });
    }

    // Get user data
    const userResponse = await fetch(`${API_BASE_URL}/api/v1/auth/me`, {
      headers: {
        Authorization: `Bearer ${authData.access_token}`,
      },
    });

    const user: User = await userResponse.json();

    return {
      success: true,
      data: { user },
    };
  } catch (error) {
    console.error("Registration error:", error);
    return {
      success: false,
      error: "An unexpected error occurred",
    };
  }
}

/**
 * Refresh the access token using the refresh token.
 * Call this when you get a 401 response.
 */
export async function refreshAccessToken(): Promise<boolean> {
  const cookieStore = await cookies();
  const refreshToken = cookieStore.get("refresh_token")?.value;

  if (!refreshToken) {
    return false;
  }

  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!response.ok) {
      // Refresh token expired - clear cookies and redirect to login
      cookieStore.delete("access_token");
      cookieStore.delete("refresh_token");
      return false;
    }

    const data: AuthResponse = await response.json();

    // Update cookies with new tokens
    cookieStore.set("access_token", data.access_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      maxAge: 60 * 60 * 8, // 8 hours
      path: "/",
    });

    if (data.refresh_token) {
      cookieStore.set("refresh_token", data.refresh_token, {
        httpOnly: true,
        secure: process.env.NODE_ENV === "production",
        sameSite: "lax",
        maxAge: 60 * 60 * 24 * 30, // 30 days
        path: "/",
      });
    }

    return true;
  } catch {
    return false;
  }
}

/**
 * Retrieve the access token from httpOnly cookies.
 * Use this in client components that need the JWT (e.g., WebSocket authentication).
 * Returns null if no token is available.
 */
export async function getAccessToken(): Promise<string | null> {
  const cookieStore = await cookies();
  return cookieStore.get("access_token")?.value ?? null;
}

export async function logout(): Promise<void> {
  const cookieStore = await cookies();
  cookieStore.delete("access_token");
  cookieStore.delete("refresh_token");
  redirect("/login");
}

export async function getCurrentUser(): Promise<User | null> {
  const cookieStore = await cookies();
  let token = cookieStore.get("access_token")?.value;

  if (!token) {
    // Try to refresh token
    const refreshed = await refreshAccessToken();
    if (!refreshed) {
      return null;
    }
    // Get the new token
    token = (await cookies()).get("access_token")?.value;
    if (!token) {
      return null;
    }
  }

  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/me`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
      cache: "no-store",
    });

    if (!response.ok) {
      // If 401, try to refresh and retry
      if (response.status === 401) {
        const refreshed = await refreshAccessToken();
        if (refreshed) {
          const newToken = (await cookies()).get("access_token")?.value;
          if (newToken) {
            const retryResponse = await fetch(`${API_BASE_URL}/api/v1/auth/me`, {
              headers: {
                Authorization: `Bearer ${newToken}`,
              },
              cache: "no-store",
            });
            if (retryResponse.ok) {
              return retryResponse.json();
            }
          }
        }
      }
      return null;
    }

    return response.json();
  } catch {
    return null;
  }
}

const requestPasswordResetSchema = z.object({
  email: z.string().email("Invalid email address"),
});

export async function requestPasswordReset(
  _prevState: ActionResult,
  formData: FormData
): Promise<ActionResult<Record<string, never>>> {
  const rawData = {
    email: formData.get("email") as string,
  };

  const validatedData = requestPasswordResetSchema.safeParse(rawData);

  if (!validatedData.success) {
    const errors = validatedData.error.flatten();
    const firstError = errors.fieldErrors.email?.[0] || "Validation failed";
    return {
      success: false,
      error: firstError,
    };
  }

  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/forgot-password`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ email: validatedData.data.email }),
    });

    if (!response.ok) {
      const error = await response.json();
      return {
        success: false,
        error: error.detail || "Failed to send reset email",
      };
    }

    return {
      success: true,
      data: {},
    };
  } catch {
    return {
      success: false,
      error: "Network error. Please try again.",
    };
  }
}

const resetPasswordSchema = z.object({
  password: z
    .string()
    .min(8, "Password must be at least 8 characters")
    .regex(/[A-Z]/, "Password must contain an uppercase letter")
    .regex(/[a-z]/, "Password must contain a lowercase letter")
    .regex(/[0-9]/, "Password must contain a number"),
  token: z.string().min(1, "Reset token is required"),
});

export async function resetPassword(
  _prevState: ActionResult,
  formData: FormData
): Promise<ActionResult<Record<string, never>>> {
  const rawData = {
    password: formData.get("password") as string,
    token: formData.get("token") as string,
  };

  const validatedData = resetPasswordSchema.safeParse(rawData);

  if (!validatedData.success) {
    const errors = validatedData.error.flatten();
    const firstError =
      errors.fieldErrors.password?.[0] ||
      errors.fieldErrors.token?.[0] ||
      "Validation failed";
    return {
      success: false,
      error: firstError,
    };
  }

  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/reset-password`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        token: validatedData.data.token,
        new_password: validatedData.data.password,
      }),
    });

    if (!response.ok) {
      const error = await response.json();
      return {
        success: false,
        error: error.detail || "Failed to reset password",
      };
    }

    return {
      success: true,
      data: {},
    };
  } catch {
    return {
      success: false,
      error: "Network error. Please try again.",
    };
  }
}