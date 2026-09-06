import { test, expect } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";

const child1 =
  "dc9506bb1d703f455def753c4a92793a98befa01114871216c901eacf7204544";

test("real preserved evidence: first birth → rejected SEND → admitted PROPOSE → two-parent lineage → integrity", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (e) => {
    if (e.type() === "error") errors.push(e.text());
  });
  await page.goto("/?tick=15");
  await expect(page.getByTestId("metric-births")).toHaveText("01");
  await page
    .getByRole("button", { name: "Child 01, Born · not active" })
    .click();
  await expect(page.getByRole("complementary")).toContainText("Founder C");
  await expect(page.getByRole("complementary")).toContainText("Founder B");
  await expect(
    page.getByRole("complementary").locator(".agent-facts"),
  ).toContainText("Birth tick15");
  await expect(
    page.getByRole("complementary").locator(".agent-facts"),
  ).toContainText("First active tick16");
  await page.getByRole("button", { name: "Next tick", exact: true }).click();
  await expect(page.getByRole("complementary")).toContainText("SEND attempted");
  await expect(page.getByRole("complementary")).toContainText(
    "Rejected by Law",
  );
  await expect(page.getByRole("complementary")).toContainText(
    "No message committed",
  );
  await expect(
    page.locator(`[data-edge-kind="message"][data-source="${child1}"]`),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Next tick", exact: true }).click();
  await expect(
    page.getByRole("complementary").locator(".inspector-attempt").first(),
  ).toContainText("PROPOSE attempted");
  await expect(
    page.getByRole("complementary").locator(".inspector-attempt").first(),
  ).toContainText("Admitted by Law");
  await expect(
    page.locator(`[data-edge-kind="proposal"][data-source="${child1}"]`),
  ).toHaveCount(1);
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Lineage", exact: true })
    .click();
  await expect(page.locator(`[data-child="${child1}"]`)).toHaveAttribute(
    "data-parents",
    "EXP000_FOUNDER_C,EXP000_FOUNDER_B",
  );
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Evidence", exact: true })
    .click();
  await expect(
    page.getByText("Locally verified", { exact: true }),
  ).toBeVisible();
  await page
    .locator("summary")
    .filter({ hasText: "Archive identities" })
    .click();
  await expect(
    page.getByText(
      "dc7f904957a90be998df603b78c993b5ebdb55ccdd4d0aa20949dca80a9df227",
      { exact: true },
    ),
  ).toBeVisible();
  await page
    .locator("summary")
    .filter({ hasText: "Recorded completion" })
    .click();
  await expect(
    page.getByText(
      "9b8d4f63a3ae3311e6a3893928f3a971b3cfb6af20c80413f66cfbe0953af4d7",
      { exact: true },
    ),
  ).toBeVisible();
  await expect(
    page.getByText(
      "e8dca7b47bb4239ec3210a6f0fbbb7a9bfe376a440634f3307e05fa9b95966b5",
      { exact: true },
    ),
  ).toBeVisible();
  expect(errors).toEqual([]);
});

for (const width of [1440, 1280]) {
  test(`real-data visual inspection captures at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: width === 1280 ? 900 : 1050 });
    const directory = resolve(`../.observatory-cache/screenshots/${width}`);
    await mkdir(directory, { recursive: true });
    await page.goto("/?tick=17");
    await expect(
      page.getByRole("group", { name: "Interaction topology at tick 17" }),
    ).toBeVisible();
    await page.screenshot({
      path: `${directory}/01-overview.png`,
      fullPage: true,
    });
    await page.getByRole("spinbutton", { name: "Jump to tick" }).fill("15");
    await expect(
      page.getByRole("button", { name: "Child 01, Born · not active" }),
    ).toBeVisible();
    const nodeBottom = await page.locator(`[data-agent-id="${child1}"]`).evaluate(
      (element) => element.getBoundingClientRect().bottom,
    );
    const dockTop = await page.locator(".replay-dock").evaluate(
      (element) => element.getBoundingClientRect().top,
    );
    expect(nodeBottom).toBeLessThan(dockTop);
    await page.screenshot({
      path: `${directory}/02-first-birth.png`,
      fullPage: true,
    });
    await page
      .getByRole("button", { name: "Child 01, Born · not active" })
      .click();
    await expect(page.getByRole("complementary")).toContainText(
      "First active tick",
    );
    await page.screenshot({
      path: `${directory}/03-child-inspector.png`,
      fullPage: true,
    });
    await page
      .getByRole("navigation")
      .getByRole("button", { name: "Lineage", exact: true })
      .click();
    await expect(
      page.getByRole("group", { name: "Two-parent lineage" }),
    ).toBeVisible();
    await page.screenshot({
      path: `${directory}/04-lineage.png`,
      fullPage: true,
    });
    await page
      .getByRole("navigation")
      .getByRole("button", { name: "Evidence", exact: true })
      .click();
    await expect(
      page.getByText("Locally verified", { exact: true }),
    ).toBeVisible();
    await page.screenshot({
      path: `${directory}/05-evidence.png`,
      fullPage: true,
    });
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth > innerWidth,
    );
    expect(overflow).toBe(false);
  });
}
