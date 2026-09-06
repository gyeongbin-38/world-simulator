import { test, expect } from "@playwright/test";
import type { Page } from "@playwright/test";

const child1 =
  "dc9506bb1d703f455def753c4a92793a98befa01114871216c901eacf7204544";
const child2 =
  "11ebd37d5eabb4e00a61e6e07045aba6a3bb0cd8774f2b220f5826c06441b07f";
const run = "WORLD_EXP000_LIVE_GROUNDING_PILOT_V1_R1";
const tickURL = (tick: number) => `/api/runs/${run}/ticks/${tick}`;
async function atTick(page: Page, tick: number) {
  await page.goto(`/?tick=${tick}`);
  await expect(
    page.getByRole("group", { name: `Interaction topology at tick ${tick}` }),
  ).toBeVisible();
}
async function seek(page: Page, tick: number) {
  await page
    .getByRole("spinbutton", { name: "Jump to tick" })
    .fill(String(tick));
  await expect(
    page.getByRole("group", { name: `Interaction topology at tick ${tick}` }),
  ).toBeVisible();
}

test("loading state is meaningful", async ({ page }) => {
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/api/runs", async (route) => {
    await gate;
    await route.continue();
  });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Opening the Observatory…" }),
  ).toBeVisible();
  release();
  await expect(
    page.getByRole("group", { name: "Interaction topology at tick 0" }),
  ).toBeVisible();
});

test("empty evidence has an actionable state", async ({ page }) => {
  await page.route("**/api/runs", (route) =>
    route.fulfill({ json: { runs: [] } }),
  );
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "A world is waiting to be observed." }),
  ).toBeVisible();
  await expect(page.getByText(/WORLD_OBSERVATORY_DATA_ROOT/)).toBeVisible();
  await expect(page.getByRole("slider")).toHaveCount(0);
});

test("integrity error withholds the world", async ({ page }) => {
  await page.route("**/api/runs", (route) =>
    route.fulfill({
      status: 409,
      json: { error: "Integrity Conflict", detail: "Archive SHA-256 mismatch" },
    }),
  );
  await page.goto("/");
  await expect(page.getByRole("alert")).toContainText(
    "Archive SHA-256 mismatch",
  );
  await expect(
    page.getByRole("heading", { name: "Integrity Conflict" }),
  ).toBeVisible();
  await expect(page.getByRole("slider")).toHaveCount(0);
});

test("real overview shows selected metrics without future agents", async ({
  page,
}) => {
  await atTick(page, 14);
  await expect(page.getByTestId("metric-living-agents")).toHaveText("03");
  await expect(page.getByTestId("metric-births")).toHaveText("00");
  await expect(page.getByTestId("metric-generation-depth")).toHaveText("00");
  await expect(page.locator(`[data-agent-id="${child1}"]`)).toHaveCount(0);
  await expect(page.locator(`[data-agent-id="${child2}"]`)).toHaveCount(0);
  await expect(
    page.getByText(
      "Layout represents interaction topology, not physical position.",
    ),
  ).toBeVisible();
});

test("replay, speed, slider and keyboard use only GET observation requests", async ({
  page,
}) => {
  const methods: string[] = [];
  page.on("request", (req) => {
    if (req.url().includes("/api/")) methods.push(req.method());
  });
  await atTick(page, 14);
  await page.getByRole("button", { name: "Next tick", exact: true }).click();
  await expect(page.getByTestId("metric-births")).toHaveText("01");
  await page
    .getByRole("button", { name: "Previous tick", exact: true })
    .click();
  await expect(page.getByTestId("metric-births")).toHaveText("00");
  await page.locator("h1").click();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByTestId("selected-tick")).toHaveText("15 / 20");
  await page.getByRole("combobox", { name: "Replay speed" }).selectOption("4");
  await page.locator("h1").click();
  await page.keyboard.press("Space");
  await expect(
    page.getByRole("button", { name: "Pause replay" }),
  ).toBeVisible();
  await expect
    .poll(async () => Number(await page.getByRole("slider").inputValue()))
    .toBeGreaterThan(15);
  await page.getByRole("button", { name: "Pause replay" }).click();
  await page.getByRole("slider").fill("15");
  await expect(page.getByTestId("metric-living-agents")).toHaveText("04");
  expect(new Set(methods)).toEqual(new Set(["GET"]));
});

test("inspector identity copy and born-versus-active semantics", async ({
  page,
}) => {
  await atTick(page, 15);
  await page
    .getByRole("button", { name: "Child 01, Born · not active" })
    .click();
  const inspector = page.getByRole("complementary", {
    name: "Child 01 Inspector",
  });
  await expect(
    inspector.getByText("Born · not active", { exact: true }),
  ).toBeVisible();
  await expect(
    inspector.getByText("No recorded actions through tick 15."),
  ).toBeVisible();
  await expect(inspector.getByText("Founder B", { exact: true })).toBeVisible();
  await expect(inspector.getByText("Founder C", { exact: true })).toBeVisible();
  await inspector.getByText("Canonical identity", { exact: false }).click();
  await expect(inspector.locator(".canonical-id")).toHaveText(child1);
  await inspector.getByRole("button", { name: "Copy ID", exact: true }).click();
  await expect(inspector.getByRole("status")).toHaveText("Copied");
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(
    child1,
  );
  await seek(page, 14);
  await expect(page.getByRole("complementary")).toHaveCount(0);
  await expect(page.locator(`[data-agent-id="${child1}"]`)).toHaveCount(0);
});

test("rejected SEND cannot appear as a committed message edge", async ({
  page,
  request,
}) => {
  await atTick(page, 16);
  await page.getByRole("button", { name: "Child 01, Active / alive" }).click();
  const inspector = page.getByRole("complementary");
  await expect(
    inspector.getByText("SEND attempted", { exact: true }),
  ).toBeVisible();
  await expect(
    inspector.getByText("Rejected by Law", { exact: true }),
  ).toBeVisible();
  await expect(
    inspector.getByText("No message committed", { exact: true }),
  ).toBeVisible();
  await expect(
    page.locator(`[data-edge-kind="message"][data-source="${child1}"]`),
  ).toHaveCount(0);
  await expect(page.locator(".attempt-note")).toContainText(
    "No canonical interaction edge created.",
  );
  await inspector.getByRole("button", { name: "Inspect evidence" }).click();
  const dialog = page.getByRole("dialog");
  const frame = await (await request.get(tickURL(16))).json();
  const source = await (await request.get(`/api/runs/${run}/evidence/${frame.evidence_ref}?tick=16`)).json();
  const exactInteger = source.content.match(/"uniform_numerator":\s*(\d+)/)?.[1];
  expect(exactInteger.length).toBeGreaterThan(16);
  await expect(dialog.locator(".raw-content")).toContainText(
    exactInteger,
  );
  await expect(dialog).toContainText("SHA-256 re-verified on read");
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
});

test("lineage has exact two-parent relations and hides future children", async ({
  page,
}) => {
  await atTick(page, 15);
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Lineage", exact: true })
    .click();
  const link = page.locator(`[data-child="${child1}"]`);
  await expect(link).toHaveAttribute(
    "data-parents",
    "EXP000_FOUNDER_C,EXP000_FOUNDER_B",
  );
  await expect(page.locator(`[data-child="${child2}"]`)).toHaveCount(0);
  await page
    .getByRole("button", { name: "Child 01, Born · not active" })
    .click();
  await expect(page.getByRole("complementary")).toContainText(
    "Two canonical parents",
  );
});

test("timeline filters, search and event seek", async ({ page }) => {
  await atTick(page, 18);
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Timeline", exact: true })
    .click();
  await page
    .getByRole("combobox", { name: "Event type" })
    .selectOption("birth");
  await expect(page.locator(".event-row")).toHaveCount(1);
  await expect(page.locator(".event-row")).toContainText("Child 01");
  await page
    .getByRole("searchbox", { name: "Search timeline" })
    .fill("missing");
  await expect(
    page.getByText("No matching activity at or before this tick."),
  ).toBeVisible();
  await page.getByRole("searchbox").fill("");
  await page.locator(".event-row").click();
  await expect(page.getByTestId("selected-tick")).toHaveText("15 / 20");
  await expect(page.getByRole("complementary")).toContainText(
    "Born · not active",
  );
});

test("evidence distinguishes local checks, recorded gates and full-run counts", async ({
  page,
}) => {
  await atTick(page, 16);
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Evidence", exact: true })
    .click();
  await expect(
    page.getByText("Locally verified", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("combobox", { name: "Filter evidence by agent" })
    .selectOption(child1);
  await page.locator(".decision-record summary").click();
  await expect(page.locator(".decision-record")).toContainText("SEND selected");
  await expect(page.locator(".decision-record")).toContainText(
    "Rejected by Law",
  );
  await page
    .getByText("Recorded completion & grounding gates", { exact: false })
    .click();
  await expect(
    page.getByText("LIVE_GROUNDING_PILOT_COMPLETE", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText(
      "e8dca7b47bb4239ec3210a6f0fbbb7a9bfe376a440634f3307e05fa9b95966b5",
      { exact: true },
    ),
  ).toBeVisible();
  await page.locator("summary").filter({ hasText: "Final result" }).click();
  await expect(page.locator(".outcome-note")).toContainText(
    "16 SEND selections → 9 committed messages.",
  );
  await expect(page.locator(".outcome-note")).toContainText(
    "5 ACCEPT selections → 2 births.",
  );
});

test("terminal boundary has no invented cognition for Child 02", async ({
  page,
}) => {
  await atTick(page, 20);
  await expect(page.getByTestId("metric-living-agents")).toHaveText("02");
  await expect(page.getByTestId("metric-natural-deaths")).toHaveText("03");
  await page.getByRole("button", { name: "Child 02, Active / alive" }).click();
  await expect(page.getByRole("complementary")).toContainText(
    "No cognition is recorded for this agent within the run horizon.",
  );
  await expect(page.getByRole("complementary")).toContainText(
    "No recorded actions through tick 20.",
  );
  await expect(
    page.getByRole("button", { name: "Next tick", exact: true }),
  ).toBeDisabled();
});

test("out-of-order responses cannot show stale agents under a new tick", async ({
  page,
  request,
}) => {
  const delayedFrame = await (await request.get(tickURL(16))).json();
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route(`**${tickURL(16)}`, async (route) => {
    await gate;
    await route.fulfill({ json: delayedFrame }).catch(() => {});
  });
  await atTick(page, 15);
  await page.getByRole("button", { name: "Next tick", exact: true }).click();
  await expect(
    page.getByRole("status", { name: "Loading tick 16" }),
  ).toBeVisible();
  await page.getByRole("spinbutton", { name: "Jump to tick" }).fill("14");
  await expect(
    page.getByRole("group", { name: "Interaction topology at tick 14" }),
  ).toBeVisible();
  release();
  await expect(page.getByTestId("selected-tick")).toHaveText("14 / 20");
  await expect(page.locator(`[data-agent-id="${child1}"]`)).toHaveCount(0);
});

test("failed observation pauses playback and withholds stale frame", async ({
  page,
}) => {
  await page.route(`**${tickURL(16)}`, (route) =>
    route.fulfill({ status: 503, json: { error: "Evidence unavailable" } }),
  );
  await atTick(page, 15);
  await page.getByRole("button", { name: "Play replay", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Evidence unavailable");
  await expect(
    page.getByRole("button", { name: "Play replay", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("group", { name: /Interaction topology/ }),
  ).toHaveCount(0);
});

test("node positions remain stable and reduced motion is respected", async ({
  page,
}) => {
  await atTick(page, 14);
  const pos = await page
    .locator('[data-agent-id="EXP000_FOUNDER_B"]')
    .getAttribute("transform");
  await seek(page, 15);
  await expect(
    page.locator('[data-agent-id="EXP000_FOUNDER_B"]'),
  ).toHaveAttribute("transform", pos!);
  expect(
    await page.evaluate(
      () => matchMedia("(prefers-reduced-motion: reduce)").matches,
    ),
  ).toBe(true);
  await page.locator(`[data-agent-id="${child1}"]`).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("complementary")).toBeVisible();
});
