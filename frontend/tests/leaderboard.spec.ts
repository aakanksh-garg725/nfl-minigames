import { test, expect } from "@playwright/test";
import { SLOTS } from "../lib/types";

test("current-week leaderboard opens read-only player lineups on desktop and mobile", async ({
  page,
}) => {
  await page.route("**/api/v1/week/**", (route) =>
    route.fulfill({ json: { season: 2026, week: 3, slots: [] } }),
  );
  let fail = false;
  await page.route("**/api/v1/leaderboards/**", (route) => {
    if (route.request().url().includes("/lineups/")) {
      if (fail)
        return route.fulfill({
          status: 404,
          json: {
            detail: "Only current-week leaderboard lineups can be viewed.",
          },
        });
      return route.fulfill({
        json: {
          season: 2026,
          week: 3,
          username: "rival_fan",
          display_name: "Rival Fan",
          favorite_team: "BAL",
          score: 60,
          status: "LIVE",
          slots: SLOTS.map((slot, i) => ({
            slot,
            actual_ppr: 10,
            game_status: "LIVE",
            player: {
              id: `player-${i}`,
              name: `Player ${i + 1}`,
              team: "BAL",
              position: slot.startsWith("WR") ? "WR" : "RB",
              projection: 12,
              opponent: "KC",
              is_home: i % 2 === 0,
            },
          })),
        },
      });
    }
    return route.fulfill({
      json: {
        season: 2026,
        week: 3,
        status: "LIVE",
        rows: [
          {
            user_id: "other",
            username: "rival_fan",
            display_name: "Rival Fan",
            rank: 1,
            score: 60,
            weeks_played: 1,
            average: 60,
          },
        ],
      },
    });
  });
  await page.goto("/leaderboard");
  const link = page.getByRole("link", {
    name: "View @rival_fan's Week 3 lineup",
    exact: true,
  });
  await expect(link).toBeVisible();
  await page.getByLabel("Week", { exact: true }).selectOption("2");
  await expect(page.locator(".leaderboard-lineup-link")).toHaveCount(0);
  await page.getByLabel("Week", { exact: true }).selectOption("3");
  await page.getByRole("tab", { name: "Season", exact: true }).click();
  await expect(page.locator(".leaderboard-lineup-link")).toHaveCount(0);
  await page.getByRole("tab", { name: "Weekly", exact: true }).click();
  await link.click();
  await expect(page).toHaveURL(/\/leaderboard\/2026\/3\/other$/);
  await expect(
    page.getByRole("heading", { name: "@rival_fan's lineup" }),
  ).toBeVisible();
  await expect(
    page.getByRole("region", { name: "Player lineup summary" }),
  ).toContainText("60.0");
  await expect(page.locator(".roster-card.filled")).toHaveCount(6);
  await expect(page.locator(".lineup-cards").getByRole("link")).toHaveCount(0);
  await expect(page.locator(".lineup-cards").getByRole("button")).toHaveCount(
    0,
  );
  await expect(page.locator(".player-matchup").first()).toContainText("vs KC");
  await expect(page.locator(".player-matchup").nth(1)).toContainText("@ KC");
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBeTruthy();
    await page.screenshot({
      path: `../artifacts/leaderboard-lineup-${width}.png`,
      fullPage: true,
    });
  }
  await page.reload();
  await expect(page.locator(".roster-card.filled")).toHaveCount(6);
  fail = true;
  await page.reload();
  await expect(
    page.getByRole("alert").filter({ hasText: "Only current-week" }),
  ).toBeVisible();
  await expect(page.locator(".roster-card")).toHaveCount(0);
  fail = false;
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(page.locator(".roster-card.filled")).toHaveCount(6);
  await page.getByRole("link", { name: "Back to leaderboard" }).click();
  await expect(link).toBeVisible();
});
