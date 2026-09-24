// Read-only local UI smoke check. All Supabase auth requests are intercepted.
import { chromium, expect } from "@playwright/test";
const browser = await chromium.launch({ channel: "chromium" });
try {
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1000 },
  });
  let signups = 0;
  let passwordChanges = 0;
  let emailChanges = 0;
  const user = {
    id: "00000000-0000-4000-8000-000000000099",
    email: "test@example.invalid",
    email_confirmed_at: new Date().toISOString(),
    identities: [],
    user_metadata: {},
    app_metadata: { provider: "email" },
    aud: "authenticated",
    created_at: new Date().toISOString(),
  };
  const token = [
    Buffer.from(JSON.stringify({ alg: "HS256", typ: "JWT" })).toString(
      "base64url",
    ),
    Buffer.from(
      JSON.stringify({
        sub: user.id,
        exp: Math.floor(Date.now() / 1000) + 3600,
        aud: "authenticated",
        role: "authenticated",
      }),
    ).toString("base64url"),
    "mock-signature",
  ].join(".");
  const session = {
    access_token: token,
    refresh_token: "mock-refresh",
    expires_in: 3600,
    token_type: "bearer",
    user,
  };
  let profile = {
    user_id: user.id,
    username: "",
    display_name: "",
    favorite_team: null,
    profile_complete: false,
    is_admin: false,
    teams: [
      { code: "BAL", name: "Baltimore Ravens" },
      { code: "SEA", name: "Seattle Seahawks" },
    ],
  };
  // No authenticated requests (including mock tokens) ever reach the real backend.
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.includes("username-availability"))
      return route.fulfill({ json: { available: true, suggestions: [] } });
    if (path.endsWith("/profile")) {
      if (route.request().method() === "PATCH")
        profile = {
          ...profile,
          ...route.request().postDataJSON(),
          profile_complete: true,
        };
      return route.fulfill({ json: profile });
    }
    return route.fulfill({
      json: { season: 2026, week: 3, slots: [], entry: null, next_slot: "RB1" },
    });
  });
  await page.route("**/auth/v1/**", async (route) => {
    if (new URL(route.request().url()).pathname.endsWith("/logout"))
      return route.fulfill({ status: 204 });
    if (route.request().url().includes("/signup")) {
      signups++;
      const body = route.request().postDataJSON();
      if (body.data?.username)
        throw new Error("Signup must not pre-create a username.");
      return route.fulfill({ json: { ...user, email_confirmed_at: null } });
    }
    if (route.request().url().includes("/token"))
      return route.fulfill({ json: session });
    if (new URL(route.request().url()).pathname.endsWith("/user")) {
      if (route.request().method() === "PUT") {
        const body = route.request().postDataJSON();
        if (body.password) passwordChanges++;
        if (body.email) emailChanges++;
      }
      return route.fulfill({ json: user });
    }
    return route.fulfill({
      status: 400,
      json: { message: "Auth call intercepted by UI test." },
    });
  });
  await page.goto("http://127.0.0.1:3000/signup");
  const header = page.locator(".topbar");
  for (const width of [1440, 800, 390, 320]) {
    await page.setViewportSize({ width, height: 1000 });
    await expect(
      header.getByRole("link", { name: "Sign in", exact: true }),
    ).toBeInViewport({ ratio: 1 });
    await expect(
      header.getByRole("link", { name: "Sign up", exact: true }),
    ).toHaveCount(0);
    expect(
      await header.evaluate((el) => el.scrollWidth <= el.clientWidth),
    ).toBeTruthy();
  }
  await header.getByRole("link", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.locator('.auth-switch a[href="/signup"]').click();
  await expect(page).toHaveURL(/\/signup$/);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await expect(page.getByLabel("Email address")).toBeVisible();
  const confirmationFeedback = page.locator(".password-match");
  await expect(confirmationFeedback).toHaveText(
    "Enter the same password again.",
  );
  await expect(page.locator('input[name="username"]')).toHaveCount(0);
  await page.getByLabel("Email address").fill("test@example.invalid");
  await page.getByLabel("Password", { exact: true }).fill("NoSymbols9");
  await page.getByLabel("Confirm password", { exact: true }).fill("NoSymbols9");
  await page.getByRole("button", { name: "Create my account" }).click();
  await expect(page.locator(".auth-card").getByRole("alert")).toContainText(
    "special character",
  );
  await page.getByLabel("Password", { exact: true }).fill("SundayVault9!");
  await page
    .getByLabel("Confirm password", { exact: true })
    .fill("Different9!");
  await expect(confirmationFeedback).toHaveText("Passwords do not match");
  await expect(confirmationFeedback).toHaveClass(/unmet/);
  await expect(confirmationFeedback).toHaveCSS("color", "rgb(242, 148, 148)");
  await expect(confirmationFeedback.locator("svg")).toHaveClass(/lucide-x/);
  await page.getByRole("button", { name: "Create my account" }).click();
  await expect(page.locator(".auth-card").getByRole("alert")).toContainText(
    "do not match",
  );
  if (signups !== 0) throw new Error("Invalid passwords reached signup.");
  await page
    .getByLabel("Confirm password", { exact: true })
    .fill("SundayVault9!");
  await expect(confirmationFeedback).toHaveText("Passwords match");
  await expect(confirmationFeedback).toHaveCSS("color", "rgb(168, 201, 147)");
  await expect(confirmationFeedback.locator("svg")).toHaveClass(/lucide-check/);
  // Editing the original password must also update confirmation immediately.
  await page.getByLabel("Password", { exact: true }).fill("ChangedVault9!");
  await expect(confirmationFeedback).toHaveText("Passwords do not match");
  await page.getByLabel("Password", { exact: true }).fill("SundayVault9!");
  await expect(confirmationFeedback).toHaveText("Passwords match");
  await page.getByRole("button", { name: "Create my account" }).click();
  await expect(
    page.getByText("Check your inbox to verify your email.", { exact: false }),
  ).toBeVisible();
  if (signups !== 1) throw new Error("Expected one mocked signup.");
  await page.screenshot({
    path: "artifacts/signup-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: "artifacts/signup-mobile.png",
    fullPage: true,
  });
  await page.goto("http://127.0.0.1:3000/login");
  await page.getByLabel("Email address").fill(user.email);
  await page.getByLabel("Password", { exact: true }).fill("CurrentPass9!");
  await page.locator("form").getByRole("button", { name: "Sign in" }).click();
  await expect(
    page.getByRole("heading", { name: "Finish your profile" }),
  ).toBeVisible();
  await expect(header.getByRole("button", { name: "Sign out" })).toBeVisible();
  await expect(header.locator(".header-auth-actions")).toHaveCount(0);
  await page.getByLabel("Username", { exact: true }).fill("vault_tester");
  await page.getByLabel("Favorite NFL team").selectOption("BAL");
  await page.getByRole("button", { name: "Save profile" }).click();
  await expect(
    page.getByRole("heading", { name: "Your profile", exact: true }),
  ).toBeVisible();
  const security = page.locator(".account-settings");
  const passwordForm = security.locator("form").filter({
    has: page.getByRole("heading", { name: "Change password", exact: true }),
  });
  await passwordForm.getByLabel("Current password").fill("CurrentPass9!");
  await passwordForm
    .getByLabel("New password", { exact: true })
    .fill("SundayVault9!");
  await passwordForm
    .getByLabel("Confirm password", { exact: true })
    .fill("Mismatch9!");
  await expect(passwordForm.locator(".password-match")).toHaveText(
    "Passwords do not match",
  );
  await passwordForm.getByRole("button", { name: "Change password" }).click();
  await expect(security.getByRole("alert")).toContainText("do not match");
  if (passwordChanges) throw new Error("Mismatched passwords reached auth.");
  await passwordForm
    .getByLabel("Confirm password", { exact: true })
    .fill("SundayVault9!");
  await expect(passwordForm.locator(".password-match")).toHaveText(
    "Passwords match",
  );
  await passwordForm.getByRole("button", { name: "Change password" }).click();
  await expect(security.getByRole("status")).toContainText(
    "password has been updated",
  );
  if (passwordChanges !== 1) throw new Error("Password update failed.");
  const emailForm = security.locator("form").filter({
    has: page.getByRole("heading", { name: "Change email", exact: true }),
  });
  await emailForm.getByLabel("New email address").fill("new@example.invalid");
  await emailForm.getByLabel("Current password").fill("SundayVault9!");
  await emailForm.getByRole("button", { name: "Change email" }).click();
  await expect(security.getByRole("status")).toContainText(
    "confirmation links",
  );
  if (emailChanges !== 1) throw new Error("Email update failed.");
  await page.screenshot({
    path: "artifacts/profile-account-mobile.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({
    path: "artifacts/profile-account-desktop.png",
    fullPage: true,
  });
  await header.getByRole("button", { name: "Sign out" }).click();
  await expect(
    header.getByRole("link", { name: "Sign in", exact: true }),
  ).toBeVisible();
  await expect(
    header.getByRole("link", { name: "Sign up", exact: true }),
  ).toHaveCount(0);
  await expect(header.getByRole("button", { name: "Sign out" })).toHaveCount(0);
  console.log(
    "Mocked auth UI passed: responsive guest header, sign-in/sign-up navigation, sign-out, live password matching, signup policy/confirmation, verified-user profile setup, password change, and email change. No real auth or profile requests sent.",
  );
} finally {
  await browser.close();
}
