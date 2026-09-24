import { supabase } from "./supabase";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public suggestions: string[] = [],
  ) {
    super(message);
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (!(init.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  const session = supabase
    ? (await supabase.auth.getSession()).data.session
    : null;
  if (session) headers.set("Authorization", `Bearer ${session.access_token}`);
  let response: Response;
  try {
    response = await fetch(
      `${process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000/api/v1"}${path}`,
      { ...init, headers, cache: "no-store" },
    );
  } catch {
    throw new ApiError(
      0,
      "The game service is unavailable. Please try again shortly.",
    );
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok)
    throw new ApiError(
      response.status,
      typeof data.detail === "string"
        ? data.detail
        : "That request could not be completed.",
      Array.isArray(data.suggestions)
        ? data.suggestions.filter((value: unknown) => typeof value === "string")
        : [],
    );
  return data as T;
}

export const post = <T>(path: string, body: unknown = {}) =>
  api<T>(path, { method: "POST", body: JSON.stringify(body) });
export const points = (value: number | null | undefined) =>
  (value ?? 0).toFixed(1);
export const easternTime = (value: string) =>
  new Intl.DateTimeFormat("en-US", {
    weekday: "short",
    hour: "numeric",
    minute: "2-digit",
    timeZone: "America/New_York",
    timeZoneName: "short",
  }).format(new Date(value));
