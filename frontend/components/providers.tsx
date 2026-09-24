"use client";

import {
  QueryClient,
  QueryClientProvider,
  useQuery,
} from "@tanstack/react-query";
import type { User } from "@supabase/supabase-js";
import { createContext, useContext, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { practice, supabase } from "@/lib/supabase";
import type { Week } from "@/lib/types";

type Auth = {
  user: User | null;
  loading: boolean;
  signedIn: boolean;
  signOut: () => Promise<void>;
};
const AuthContext = createContext<Auth>({
  user: null,
  loading: true,
  signedIn: false,
  signOut: async () => {},
});

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: 15_000, retry: 1, refetchOnWindowFocus: true },
        },
      }),
  );
  const [user, setUser] = useState<User | null>(null);
  const userIdRef = useRef<string | undefined>(undefined);
  const [loading, setLoading] = useState(!!supabase && !practice);
  useEffect(() => {
    if (!supabase || practice) return;
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null);
      setLoading(false);
      if (userIdRef.current !== session?.user.id) queryClient.clear();
      userIdRef.current = session?.user.id;
    });
    return () => subscription.unsubscribe();
  }, [queryClient]);
  async function signOut() {
    await supabase?.auth.signOut();
    setUser(null);
    queryClient.clear();
  }
  return (
    <QueryClientProvider client={queryClient}>
      <AuthContext.Provider
        value={{ user, loading, signedIn: practice || !!user, signOut }}
      >
        {children}
      </AuthContext.Provider>
    </QueryClientProvider>
  );
}
export const useAuth = () => useContext(AuthContext);
export function useWeek() {
  const auth = useAuth();
  return useQuery({
    queryKey: ["week", auth.signedIn],
    queryFn: () => api<Week>(`/week/${auth.signedIn ? "current" : "public"}`),
    enabled: !auth.loading,
    refetchInterval: 30_000,
  });
}
