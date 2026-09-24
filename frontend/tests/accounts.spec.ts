import { test, expect } from "@playwright/test";
import { passwordRules, validatePassword } from "../lib/password";

test("password policy covers every requirement and confirmation", () => {
  const valid = "SundayVault9!";
  expect(passwordRules.every((rule) => rule.test(valid))).toBeTruthy();
  expect(() => validatePassword(valid, valid)).not.toThrow();
  for (const value of [
    "Aa1!",
    "lowercase9!",
    "UPPERCASE9!",
    "NoNumbers!",
    "NoSymbols9",
    "SpacesOnly9 ",
  ]) {
    expect(() => validatePassword(value, value)).toThrow(/at least 8/);
  }
  expect(() => validatePassword(valid, "Different9!")).toThrow(/do not match/);
});

test("play and direct game links require a saved username", async ({
  page,
}) => {
  let complete = false;
  let gameRequests = 0;
  await page.route("**/api/v1/profile", async (route) => {
    if (route.request().method() === "PATCH") {
      expect(route.request().postDataJSON().username).toBe("ready_player");
      complete = true;
    }
    await route.fulfill({
      json: {
        user_id: "onboarding",
        username: complete ? "ready_player" : "",
        display_name: "",
        favorite_team: "BAL",
        profile_complete: complete,
        is_admin: false,
        teams: [{ code: "BAL", name: "Baltimore Ravens" }],
      },
    });
  });
  await page.route("**/api/v1/deal-games**", async (route) => {
    gameRequests++;
    await route.fulfill({
      status: 500,
      json: { detail: "Unexpected game request" },
    });
  });
  for (const path of ["/play", "/play/saved-game"]) {
    await page.goto(path);
    await expect(page).toHaveURL(/\/profile$/);
    await expect(
      page.getByRole("heading", { name: "Finish your profile" }),
    ).toBeVisible();
    await expect(
      page.getByText("Before you can play, save your player profile.", {
        exact: false,
      }),
    ).toBeVisible();
    expect(gameRequests).toBe(0);
  }
  await page.getByLabel("Username", { exact: true }).fill("ready_player");
  await page.getByRole("button", { name: "Save profile" }).click();
  await expect(
    page.getByRole("heading", { name: "Your profile", exact: true }),
  ).toBeVisible();
  await page.locator('.success-notice a[href="/play"]').click();
  await expect(
    page.getByRole("heading", { name: "Build your Sunday." }),
  ).toBeVisible();
  await expect(page).toHaveURL(/\/play$/);
  expect(gameRequests).toBe(0);
});

test("profile loading errors do not expose gameplay", async ({ page }) => {
  await page.route("**/api/v1/profile", (route) =>
    route.fulfill({
      status: 503,
      json: { detail: "Profile temporarily unavailable" },
    }),
  );
  await page.goto("/play");
  await expect(
    page
      .getByRole("alert")
      .filter({ hasText: "Profile temporarily unavailable" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Build your Sunday." }),
  ).toHaveCount(0);
});

test("sidebar adapts to short screens and has no promo card", async ({
  page,
}) => {
  await page.goto("/profile");
  const sidebar = page.locator(".sidebar");
  await expect(sidebar.locator(".mini-promo")).toHaveCount(0);
  const links = sidebar.getByRole("navigation").getByRole("link");
  const names = await links.allTextContents();
  expect(names.indexOf("Head-to-head")).toBeLessThan(
    names.indexOf("My history"),
  );
  for (const height of [900, 720, 600]) {
    await page.setViewportSize({ width: 1280, height });
    await sidebar.evaluate((element) => {
      element.scrollTop = 0;
    });
    await expect(sidebar.locator(".account-link")).toBeInViewport({ ratio: 1 });
    await expect(sidebar.locator(".help-link")).toBeInViewport({ ratio: 1 });
    await expect(
      sidebar.getByRole("link", { name: "Profile", exact: true }),
    ).toBeInViewport({ ratio: 1 });
  }
  await page.screenshot({
    path: "../artifacts/sidebar-short-desktop.png",
    fullPage: false,
  });
  await page.setViewportSize({ width: 1280, height: 400 });
  await sidebar.locator(".account-link").scrollIntoViewIfNeeded();
  await expect(sidebar.locator(".account-link")).toBeInViewport({ ratio: 1 });
  expect(
    await sidebar.evaluate((element) => element.scrollTop),
  ).toBeGreaterThan(0);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(sidebar).toBeHidden();
  await expect(
    page
      .getByRole("navigation", { name: "Mobile navigation" })
      .getByRole("link", { name: "Profile", exact: true }),
  ).toBeInViewport();
});

test("profile edits, username conflicts with suggestions, favorite team, mobile sidebar", async ({
  page,
}) => {
  await page.goto("/profile");
  await expect(
    page.getByRole("heading", { name: "Your profile", exact: true }),
  ).toBeVisible();
  await expect(
    page
      .getByRole("navigation", { name: "Main navigation", exact: true })
      .getByRole("link", { name: "Profile", exact: true }),
  ).toBeVisible();
  await page.route("**/api/v1/profile", async (route) => {
    if (
      route.request().method() === "PATCH" &&
      route.request().postDataJSON().username === "taken"
    ) {
      await route.fulfill({
        status: 409,
        json: {
          detail:
            "That username is already taken. Please choose a different one.",
          suggestions: ["taken_fan", "taken_nfl", "taken_ppr"],
        },
      });
    } else await route.continue();
  });
  await page.getByLabel("Username", { exact: true }).fill("taken");
  await page.getByRole("button", { name: "Save profile" }).click();
  await expect(
    page.locator(".profile-card").first().getByRole("alert"),
  ).toContainText("already taken");
  await page.getByRole("button", { name: "@taken_fan", exact: true }).click();
  await page.getByLabel("Favorite NFL team").selectOption("SEA");
  await page.getByRole("button", { name: "Save profile" }).click();
  await expect(
    page.getByText("Profile saved.", { exact: false }),
  ).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("Username", { exact: true })).toHaveValue(
    "taken_fan",
  );
  await expect(page.getByLabel("Favorite NFL team")).toHaveValue("SEA");
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: "../artifacts/profile-mobile.png",
    fullPage: true,
  });
  // Leave the shared practice identity unchanged for the game regression test.
  await page.getByLabel("Username", { exact: true }).fill("local_player");
  await page.getByLabel("Favorite NFL team").selectOption("BAL");
  await page.getByLabel("Display name (optional)").fill("Local Player");
  await page.getByRole("button", { name: "Save profile" }).click();
  await expect(
    page.getByText("Profile saved.", { exact: false }),
  ).toBeVisible();
});

test("head-to-head invitations, record and weekly history UI", async ({
  page,
}) => {
  let accepted = false;
  await page.route("**/api/v1/rivalries**", async (route) => {
    if (route.request().url().includes("/matchups/")) {
      const week = Number(route.request().url().split("/").pop());
      const team = (username: string, name: string, score: number) => ({
        username,
        favorite_team: "BAL",
        score: week === 4 ? score : 0,
        slots:
          week === 4
            ? [
                {
                  slot: "RB1",
                  actual_ppr: score,
                  game_status: "FINAL",
                  player: {
                    id: username,
                    name,
                    position: "RB",
                    team: "BAL",
                    projection: 15.5,
                    opponent: "KC",
                    is_home: false,
                  },
                },
              ]
            : [],
      });
      return route.fulfill({
        json: {
          season: 2026,
          week,
          weeks: [4, 5],
          status: week === 4 ? "FINAL" : "UPCOMING",
          you: team("local_player", "Your running back", 100),
          opponent: team("rival_fan", "Their running back", 95),
        },
      });
    }
    if (route.request().method() === "POST") {
      expect(route.request().postDataJSON()).toEqual({ decision: "ACCEPT" });
      accepted = true;
      return route.fulfill({ json: {} });
    }
    return route.fulfill({
      json: {
        season: 2026,
        total_points: accepted ? 100 : 0,
        weeks_scored: accepted ? 1 : 0,
        record: { wins: accepted ? 1 : 0, losses: 0, ties: 0 },
        rivalries: [
          {
            id: "preview",
            season: 2026,
            status: accepted ? "ACCEPTED" : "PENDING",
            direction: "RECEIVED",
            start_week: accepted ? 3 : null,
            opponent: { username: "rival_fan", favorite_team: "SEA" },
            record: { wins: 1, losses: 0, ties: 0 },
            opponent_record: { wins: 0, losses: 1, ties: 0 },
            your_total: 100,
            opponent_total: 95,
            history: accepted
              ? [
                  {
                    week: 4,
                    status: "FINAL",
                    your_score: 100,
                    opponent_score: 95,
                    outcome: "WIN",
                    updated_at: new Date().toISOString(),
                  },
                ]
              : [],
          },
        ],
      },
    });
  });
  await page.goto("/head-to-head");
  await expect(page.getByRole("heading", { name: "@rival_fan" })).toBeVisible();
  await page.getByRole("button", { name: "Accept invitation" }).click();
  await expect(page.getByText("Weeks 3–18 · 2026 season")).toBeVisible();
  await expect(
    page.getByRole("cell", { name: "WIN", exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: "../artifacts/head-to-head-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await expect(
    page
      .getByRole("navigation", { name: "Mobile navigation" })
      .getByRole("link", { name: "H2H" }),
  ).toBeInViewport();
  await page.screenshot({
    path: "../artifacts/head-to-head-mobile.png",
    fullPage: true,
  });
  await page
    .getByRole("link", { name: "View Week 4 matchup against rival_fan" })
    .click();
  await expect(
    page.getByRole("heading", { name: "The weekly showdown." }),
  ).toBeVisible();
  await expect(
    page.getByLabel("Your total points", { exact: true }),
  ).toHaveText("100.0");
  await expect(
    page.getByLabel("Opponent total points", { exact: true }),
  ).toHaveText("95.0");
  const pair = page.getByLabel("RB1 matchup", { exact: true });
  await expect(pair.locator(".matchup-player").first()).toContainText(
    "Your running back",
  );
  await expect(pair.locator(".matchup-player").last()).toContainText(
    "Their running back",
  );
  await expect(pair).toContainText("@ KC");
  await expect(page.getByText("Empty slot", { exact: true })).toHaveCount(10);
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 950 });
    const yours = await page.locator(".your-team").boundingBox();
    const theirs = await page.locator(".opponent-team").boundingBox();
    expect(yours!.x + yours!.width).toBeLessThan(theirs!.x);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBeTruthy();
    await page.screenshot({
      path: `../artifacts/matchup-${width}.png`,
      fullPage: true,
    });
  }
  await page.getByLabel("Matchup week", { exact: true }).selectOption("5");
  await expect(page).toHaveURL(/\/preview\/5$/);
  await expect(page.getByText("Empty slot", { exact: true })).toHaveCount(12);
  await expect(
    page.getByLabel("Your total points", { exact: true }),
  ).toHaveText("0.0");
  await page.reload();
  await expect(page.getByText("UPCOMING", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Back to rivalries" }).click();
  await expect(page).toHaveURL(/\/head-to-head$/);
});
