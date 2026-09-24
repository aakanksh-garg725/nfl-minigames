import { test, expect, type Page, type Locator } from "@playwright/test";

async function expectCasePopup(page: Page, popup: Locator) {
  await expect(popup).toBeVisible();
  await expect(popup).toBeFocused();
  await expect(page.getByRole("dialog")).toHaveCount(1);
  await expect(
    page.locator(
      ".game-decision-area .dealer-card, .game-decision-area .complete-card",
    ),
  ).toHaveCount(0);
  await expect(page.locator(".case-grid button:not(:disabled)")).toHaveCount(0);
  const stage = await page.locator(".cases-stage").boundingBox();
  const dialog = await popup.boundingBox();
  const overlay = await page.locator(".game-popup-overlay").boundingBox();
  const board = await page.locator(".player-board").boundingBox();
  const history = await page.locator(".offers-panel").boundingBox();
  expect(stage && dialog && overlay && board && history).toBeTruthy();
  expect(dialog!.y).toBeGreaterThanOrEqual(stage!.y);
  expect(dialog!.y + dialog!.height).toBeLessThanOrEqual(
    stage!.y + stage!.height + 1,
  );
  expect(overlay!.x).toBeGreaterThanOrEqual(board!.x + board!.width);
  expect(overlay!.x + overlay!.width).toBeLessThanOrEqual(history!.x);
  await expect(page.locator(".player-board")).toBeInViewport();
  await expect(page.locator(".offers-panel")).toBeInViewport();
}

async function expectMobilePopup(page: Page, popup: Locator) {
  await page.setViewportSize({ width: 390, height: 844 });
  await popup.scrollIntoViewIfNeeded();
  for (const control of await popup.locator("button, a").all()) {
    await expect(control).toBeInViewport();
  }
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
}

test("responsive six-slot game, reload, offer decisions, lineup and standings", async ({
  page,
}) => {
  // Includes all four offer rounds for both KEEP and SWAP, plus reload checks.
  test.setTimeout(240_000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Make your next great call." }),
  ).toBeVisible();
  await page.screenshot({
    path: "../artifacts/home-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: "../artifacts/home-mobile.png",
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.setViewportSize({ width: 1440, height: 1080 });
  await page.goto("/play");
  for (let slot = 0; slot < 6; slot++) {
    await page
      .getByRole("button", { name: /Play for|Resume your game/ })
      .click();
    await page.waitForURL(/\/play\/.+/);
    await expect(
      page.getByRole("heading", { name: "Choose your case" }),
    ).toBeVisible();
    await expect(page.locator(".board-row .player-matchup")).toHaveCount(12);
    await expect(page.locator(".board-row .player-matchup").first()).toHaveText(
      "· vs NFL",
    );
    if (slot === 0) {
      await page.screenshot({
        path: "../artifacts/game-desktop.png",
        fullPage: true,
      });
      await page.setViewportSize({ width: 390, height: 844 });
      await page.screenshot({
        path: "../artifacts/game-mobile.png",
        fullPage: true,
      });
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
      ).toBeTruthy();
      await page
        .getByRole("button", { name: "Choose case 7", exact: true })
        .click();
      await page.reload();
      await expect(
        page.getByRole("button", { name: "Your case 7", exact: true }),
      ).toBeDisabled();
      await page.setViewportSize({ width: 1440, height: 1080 });
    } else
      await page
        .getByRole("button", { name: "Choose case 7", exact: true })
        .click();
    for (let i = 0; i < 4; i++) {
      const next = page.locator(".case-grid button:not(:disabled)").first();
      await expect(next).toBeEnabled();
      await next.click();
    }
    await expect(
      page.getByRole("button", { name: "DEAL", exact: true }),
    ).toBeVisible();
    await expect(page.locator(".case-grid button:not(:disabled)")).toHaveCount(
      0,
    );
    if (slot === 0) {
      const popup = page.getByRole("dialog", { name: "Banker offer 1" });
      await expect(popup).toBeVisible();
      await expect(popup).toBeFocused();
      await expect(
        page.locator(".game-decision-area .dealer-card"),
      ).toHaveCount(0);
      const stage = await page.locator(".cases-stage").boundingBox();
      const overlay = await page.locator(".banker-offer-overlay").boundingBox();
      const dialog = await popup.boundingBox();
      const board = await page.locator(".player-board").boundingBox();
      const history = await page.locator(".offers-panel").boundingBox();
      expect(stage && overlay && dialog && board && history).toBeTruthy();
      expect(dialog!.y).toBeGreaterThanOrEqual(stage!.y);
      expect(dialog!.y + dialog!.height).toBeLessThanOrEqual(
        stage!.y + stage!.height + 1,
      );
      expect(overlay!.x).toBeGreaterThanOrEqual(board!.x + board!.width);
      expect(overlay!.x + overlay!.width).toBeLessThanOrEqual(history!.x);
      await expect(page.locator(".player-board")).toBeInViewport();
      await expect(page.locator(".offers-panel")).toBeInViewport();
      await page.keyboard.press("Tab");
      await expect(
        popup.getByRole("button", { name: "DEAL", exact: true }),
      ).toBeFocused();
      await page.keyboard.press("Tab");
      await expect(
        popup.getByRole("button", { name: "NO DEAL", exact: true }),
      ).toBeFocused();
      await page.keyboard.press("Escape");
      await expect(popup).toBeVisible();
      const offeredPlayer = await popup.locator("h3").textContent();
      await page.reload();
      await expect(popup).toBeVisible();
      await expect(popup.locator("h3")).toHaveText(offeredPlayer!);
      await page.screenshot({
        path: "../artifacts/dealer-offer.png",
        fullPage: true,
      });
      await page.setViewportSize({ width: 390, height: 844 });
      await popup.scrollIntoViewIfNeeded();
      await expect(
        popup.getByRole("button", { name: "DEAL", exact: true }),
      ).toBeInViewport();
      await expect(
        popup.getByRole("button", { name: "NO DEAL", exact: true }),
      ).toBeInViewport();
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
      ).toBeTruthy();
      await page.screenshot({
        path: "../artifacts/dealer-offer-mobile.png",
        fullPage: true,
      });
      await page.setViewportSize({ width: 1440, height: 1080 });
      await page.getByRole("button", { name: "NO DEAL", exact: true }).click();
      await expect(popup).toHaveCount(0);
      for (let i = 0; i < 3; i++) {
        const next = page.locator(".case-grid button:not(:disabled)").first();
        await expect(next).toBeEnabled();
        await next.click();
      }
      await expect(
        page.getByRole("button", { name: "DEAL", exact: true }),
      ).toBeVisible();
    }
    if (slot === 1 || slot === 2) {
      // Exercise both final choices through real API transitions.
      for (const count of [3, 2, 1]) {
        await page
          .getByRole("button", { name: "NO DEAL", exact: true })
          .click();
        for (let i = 0; i < count; i++) {
          const next = page.locator(".case-grid button:not(:disabled)").first();
          await expect(next).toBeEnabled();
          await next.click();
        }
        await expect(
          page.getByRole("button", { name: "NO DEAL", exact: true }),
        ).toBeVisible();
      }
      await page.getByRole("button", { name: "NO DEAL", exact: true }).click();
      const finalPopup = page.getByRole("dialog", {
        name: "Stay loyal or switch sides?",
      });
      await expectCasePopup(page, finalPopup);
      await page.keyboard.press("Tab");
      await expect(
        finalPopup.getByRole("button", { name: "Keep case #7" }),
      ).toBeFocused();
      await page.keyboard.press("Tab");
      await expect(
        finalPopup.getByRole("button", { name: /Swap for/ }),
      ).toBeFocused();
      await page.reload();
      await expectCasePopup(page, finalPopup);
      await page.screenshot({
        path: "../artifacts/final-choice-desktop.png",
        fullPage: true,
      });
      await expectMobilePopup(page, finalPopup);
      await page.screenshot({
        path: "../artifacts/final-choice-mobile.png",
        fullPage: true,
      });
      await finalPopup
        .getByRole("button", { name: slot === 1 ? "Keep case #7" : /Swap for/ })
        .click();
      await expect(finalPopup).toHaveCount(0);
      await page.setViewportSize({ width: 1440, height: 1080 });
    } else {
      await page.getByRole("button", { name: "DEAL", exact: true }).click();
    }
    const lockedPopup = page.getByRole("dialog", { name: /LOCKED IN/ });
    await expectCasePopup(page, lockedPopup);
    await expect(lockedPopup.locator(".player-matchup")).toBeVisible();
    const awardedPlayer = await lockedPopup.locator("h3").textContent();
    await page.reload();
    await expectCasePopup(page, lockedPopup);
    await expect(lockedPopup.locator("h3")).toHaveText(awardedPlayer!);
    await page.keyboard.press("Tab");
    await expect(lockedPopup.getByRole("link")).toBeFocused();
    if (slot === 0 || slot === 1) {
      await page.screenshot({
        path: "../artifacts/player-locked-desktop.png",
        fullPage: true,
      });
      await expectMobilePopup(page, lockedPopup);
      await page.screenshot({
        path: "../artifacts/player-locked-mobile.png",
        fullPage: true,
      });
    }
    await lockedPopup.getByRole("link").click();
    await page.waitForURL("**/play");
    await page.setViewportSize({ width: 1440, height: 1080 });
  }
  await expect(
    page.getByText("Your six are set. Let’s play football."),
  ).toBeVisible();
  await page.getByRole("link", { name: "View my lineup", exact: true }).click();
  await expect(page.locator(".roster-card.filled")).toHaveCount(6);
  await page.screenshot({
    path: "../artifacts/lineup-desktop.png",
    fullPage: true,
  });
  await page.goto("/leaderboard");
  await expect(page.getByText("@local_player")).toBeVisible();
  await page.goto("/history");
  await expect(page.locator(".history-card")).toHaveCount(1);
  await page.locator(".history-card").click();
  await expect(page.locator(".roster-card.filled")).toHaveCount(6);
  expect(errors).toEqual([]);
});

test("player rows display vs for home and @ for away on mobile", async ({
  page,
}) => {
  const board = Array.from({ length: 12 }, (_, i) => ({
    id: `preview-${i}`,
    name: `Preview Player ${i + 1}`,
    team: "BAL",
    position: "RB",
    projection: 20 - i,
    board_rank: i + 1,
    eliminated: false,
    opponent: "CIN",
    is_home: i % 2 === 0,
  }));
  await page.route("**/api/v1/deal-games/matchup-preview", (route) =>
    route.fulfill({
      json: {
        id: "matchup-preview",
        slot: "RB1",
        status: "AWAITING_CASE_SELECTION",
        version: 0,
        expires_at: new Date(Date.now() + 86_400_000).toISOString(),
        current_round: 0,
        round_open_count: 0,
        selected_case_number: null,
        board,
        cases: board.map((_, i) => ({
          case_number: i + 1,
          status: "CLOSED",
          is_user_case: false,
        })),
        offers: [],
        instruction: "Choose your case",
        outcome: null,
        awarded_player: null,
      },
    }),
  );
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/play/matchup-preview");
  const rows = page.locator(".board-row");
  await expect(rows).toHaveCount(12);
  await expect(rows.nth(0)).toContainText("vs CIN");
  await expect(rows.nth(1)).toContainText("@ CIN");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
});
