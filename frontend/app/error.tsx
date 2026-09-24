"use client";
import { ErrorNotice } from "@/components/ui";
export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <ErrorNotice
      error={new Error("This screen couldn’t load. Your saved lineup is safe.")}
      retry={reset}
    />
  );
}
