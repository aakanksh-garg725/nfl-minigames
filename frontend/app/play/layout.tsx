"use client";

import Link from "next/link";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Profile } from "@/lib/types";
import { ErrorNotice, Loading, RequireAuth } from "@/components/ui";

function RequirePlayerProfile({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const profile = useQuery({
    queryKey: ["profile"],
    queryFn: () => api<Profile>("/profile"),
    staleTime: 0,
  });
  const ready =
    !!profile.data?.profile_complete &&
    /^[A-Za-z0-9_]{3,24}$/.test(profile.data.username);

  useEffect(() => {
    if (profile.isSuccess && !ready) router.replace("/profile");
  }, [profile.isSuccess, ready, router]);

  if (profile.isPending || (!ready && profile.isFetching))
    return <Loading label="Checking your player profile…" />;
  if (profile.error)
    return <ErrorNotice error={profile.error} retry={profile.refetch} />;
  if (!ready)
    return (
      <div className="info-notice" role="status">
        Create a unique username and choose your favorite NFL team before
        playing. <Link href="/profile">Set up your profile</Link>
      </div>
    );
  return children;
}

export default function PlayLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <RequireAuth>
      <RequirePlayerProfile>{children}</RequirePlayerProfile>
    </RequireAuth>
  );
}
