"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";
import { ErrorNotice, Loading } from "@/components/ui";
export default function AuthCallback() {
  const router = useRouter();
  const [error, setError] = useState<Error | null>(null);
  const started = useRef(false);
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    async function finish() {
      if (!supabase) {
        setError(new Error("Sign-in is not configured yet."));
        return;
      }
      const url = new URL(window.location.href);
      const callbackError =
        url.searchParams.get("error_description") ||
        new URLSearchParams(url.hash.slice(1)).get("error_description");
      if (callbackError) {
        setError(
          new Error(
            "This verification link has expired or is invalid. Try signing in or request a new verification email.",
          ),
        );
        return;
      }
      // getSession waits for the SDK's URL/session initialization first.
      const initial = await supabase.auth.getSession();
      const code = url.searchParams.get("code");
      if (code && !initial.data.session) {
        const result = await supabase.auth.exchangeCodeForSession(code);
        if (result.error) {
          setError(result.error);
          return;
        }
      }
      const { data } = await supabase.auth.getSession();
      router.replace(data.session ? "/profile" : "/login");
    }
    finish().catch(() =>
      setError(
        new Error(
          "Unable to verify your account. Please try signing in again.",
        ),
      ),
    );
  }, [router]);
  return error ? (
    <ErrorNotice error={error} />
  ) : (
    <Loading label="Confirming your account…" />
  );
}
