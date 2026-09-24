import { spawn, spawnSync } from "node:child_process";
import { resolve } from "node:path";
import { existsSync } from "node:fs";

const practice = process.argv.includes("--practice");
const isolatedTest = process.argv.includes("--test");
if (isolatedTest && !practice) {
  console.error("Isolated tests require --practice to protect the live database.");
  process.exit(1);
}
const webPort = isolatedTest ? "3100" : "3000";
const apiPort = isolatedTest ? "8100" : "8000";
const win = process.platform === "win32";
const python = resolve(win ? ".venv/Scripts/python.exe" : ".venv/bin/python");
if (!existsSync(python)) {
  console.error("Create the Python virtual environment first. See README.md.");
  process.exit(1);
}
const env = { ...process.env };
if (practice) {
  env.AUTH_MODE = "demo";
  env.DATABASE_URL = `sqlite:///./${isolatedTest ? `e2e-${Date.now()}` : "practice"}.db`;
  env.APP_ENV = "development";
  env.NEXT_PUBLIC_DEMO_MODE = "true";
}
if (isolatedTest) {
  env.CORS_ORIGINS = "http://127.0.0.1:3100";
  env.NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8100/api/v1";
  env.NEXT_BUILD_DIR = ".next-e2e";
}
const api = spawn(
  python,
  ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", apiPort],
  { cwd: resolve("backend"), env, stdio: "inherit", windowsHide: true },
);
const web = spawn(
  process.execPath,
  [
    resolve("node_modules/next/dist/bin/next"),
    "dev",
    "--hostname",
    "127.0.0.1",
    "--port",
    webPort,
  ],
  { cwd: resolve("frontend"), env, stdio: "inherit", windowsHide: true },
);
let stopping = false;
function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  for (const child of [api, web]) {
    if (!child.pid || child.exitCode !== null) continue;
    if (win) {
      // Python's venv launcher and Next.js both create child processes on Windows.
      spawnSync("taskkill", ["/PID", String(child.pid), "/T", "/F"], {
        windowsHide: true,
        stdio: "ignore",
      });
    } else child.kill("SIGTERM");
  }
  process.exitCode = code;
}
process.on("SIGINT", () => stop());
process.on("SIGTERM", () => stop());
api.on("exit", (code) => stop(code ?? 0));
web.on("exit", (code) => stop(code ?? 0));
for (const child of [api, web]) {
  child.on("error", (error) => {
    console.error(error.message);
    stop(1);
  });
}
console.log(
  `Sunday Vault: http://127.0.0.1:${webPort} (${practice ? "synthetic local practice" : "Supabase + ESPN"})`,
);
