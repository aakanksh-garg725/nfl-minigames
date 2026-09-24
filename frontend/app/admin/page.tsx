"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, post } from "@/lib/api";
import type { Profile } from "@/lib/types";
import {
  Empty,
  ErrorNotice,
  Loading,
  PageTitle,
  RequireAuth,
} from "@/components/ui";

type Health = {
  runs: {
    id: string;
    operation: string;
    status: string;
    message: string;
    created_at: string;
  }[];
  snapshots: { id: string; season: number; week: number; fetched_at: string }[];
};
function Admin() {
  const profile = useQuery({
    queryKey: ["profile"],
    queryFn: () => api<Profile>("/profile"),
  });
  const health = useQuery({
    queryKey: ["admin-health"],
    queryFn: () => api<Health>("/admin/health"),
    enabled: !!profile.data?.is_admin,
  });
  const [error, setError] = useState<unknown>();
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  async function run(task: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    setMessage("");
    try {
      await task();
      setMessage("Operation completed.");
      health.refetch();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  if (profile.isPending) return <Loading />;
  if (profile.error) return <ErrorNotice error={profile.error} />;
  if (!profile.data?.is_admin)
    return (
      <Empty title="Administrator access required">
        This area is only available to the app administrator.
      </Empty>
    );
  return (
    <>
      <PageTitle eyebrow="OPERATIONS" title="Behind the vault.">
        Provider health, manual imports, and weekly scoring controls.
      </PageTitle>
      <ErrorNotice error={error || health.error} />
      {message && (
        <div className="success-notice" role="status">
          {message}
        </div>
      )}
      <div className="admin-grid">
        <section className="panel admin-card">
          <h2>ESPN sync & scoring</h2>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget),
                op = String(f.get("operation")),
                season = f.get("season"),
                week = f.get("week");
              run(() =>
                post(
                  ["projections", "results"].includes(op)
                    ? `/admin/sync/${op}?season=${season}&week=${week}`
                    : `/admin/weeks/${season}/${week}/${op}`,
                ),
              );
            }}
          >
            <label>
              Season
              <input
                name="season"
                type="number"
                defaultValue={new Date().getFullYear()}
                min={2020}
                max={2100}
                required
              />
            </label>
            <label>
              Week
              <input
                name="week"
                type="number"
                min={1}
                max={18}
                defaultValue={3}
                required
              />
            </label>
            <label>
              Operation
              <select name="operation">
                <option value="projections">Import ESPN projections</option>
                <option value="results">Import ESPN results</option>
                <option value="recompute">Recompute scores</option>
                <option value="finalize">Finalize week</option>
                <option value="unfinalize">Unfinalize week</option>
              </select>
            </label>
            <button className="button primary" disabled={busy}>
              Run operation
            </button>
          </form>
        </section>
        <section className="panel admin-card">
          <h2>Manual CSV fallback</h2>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const form = new FormData(e.currentTarget);
              run(() => api("/admin/import", { method: "POST", body: form }));
            }}
          >
            <label>
              Season
              <input
                type="number"
                name="season"
                defaultValue={new Date().getFullYear()}
                required
              />
            </label>
            <label>
              Week
              <input
                type="number"
                name="week"
                defaultValue={3}
                min={1}
                max={18}
                required
              />
            </label>
            <label>
              Import type
              <select name="operation">
                <option value="projections">Projections</option>
                <option value="results">Actual results</option>
              </select>
            </label>
            <label>
              CSV file
              <input name="file" type="file" accept=".csv,text/csv" required />
            </label>
            <button className="button secondary" disabled={busy}>
              Import CSV
            </button>
          </form>
        </section>
      </div>
      <section className="panel admin-card admin-runs">
        <h2>Recent provider activity</h2>
        {!health.data?.runs.length && (
          <p className="muted">No provider jobs have run yet.</p>
        )}
        {health.data?.runs.map((r) => (
          <div className="provider-run" key={r.id}>
            <strong>{r.status}</strong>
            {r.operation} · {new Date(r.created_at).toLocaleString()}
            <p>{r.message}</p>
          </div>
        ))}
      </section>
      <section className="panel admin-card admin-runs">
        <h2>Latest projection snapshots</h2>
        {health.data?.snapshots.map((s) => (
          <div className="provider-run" key={s.id}>
            {s.season} · Week {s.week} ·{" "}
            {new Date(s.fetched_at).toLocaleString()}
            <p>{s.id}</p>
          </div>
        ))}
      </section>
    </>
  );
}
export default function AdminPage() {
  return (
    <RequireAuth>
      <Admin />
    </RequireAuth>
  );
}
