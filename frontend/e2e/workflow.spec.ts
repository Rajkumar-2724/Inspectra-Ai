import { expect, test, Page } from "@playwright/test";

const USER = process.env.E2E_USER ?? "admin";
const PASS = process.env.E2E_PASSWORD ?? "ChangeMe-Admin-123";

async function login(page: Page, user = USER, pass = PASS) {
  await page.goto("/login");
  await page.getByLabel(/username or email/i).fill(user);
  await page.getByLabel("Password").fill(pass);
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
}

async function runDemoInspection(page: Page, sample: string, scenarioLabel: RegExp) {
  await page.getByRole("link", { name: "AI Inspection" }).click();
  await page.getByRole("button", { name: sample }).click();
  await expect(page.getByAltText("Selected upload preview")).toBeVisible();
  await page.getByLabel("Product type").selectOption({ index: 1 });
  await page.getByLabel("Demo scenario").selectOption({ label: scenarioLabel.source.replace(/\\/g, "") });
  await page.getByRole("button", { name: /run inspection/i }).click();
  await expect(page.getByTestId("result-view")).toBeVisible({ timeout: 30_000 });
}

test("1. login rejects bad credentials and accepts good ones", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel(/username or email/i).fill(USER);
  await page.getByLabel("Password").fill("wrong-password");
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page.getByText(/incorrect username or password/i)).toBeVisible();
  await login(page);
});

test("2. dashboard shows stats and charts from the backend", async ({ page }) => {
  await login(page);
  await expect(page.getByText("Total inspections")).toBeVisible();
  await expect(page.getByText("Inspection trends (per day)")).toBeVisible();
  await expect(page.locator(".recharts-wrapper").first()).toBeVisible();
});

test("3-5. upload a demo image, inspect it and view the result visualisations", async ({ page }) => {
  await login(page);
  await runDemoInspection(page, "Obvious defect", /Obvious defect → FAIL/);
  await expect(page.getByTestId("decision")).toHaveText("FAIL");
  await expect(page.getByText(/SIMULATED RESULT/)).toBeVisible();
  for (const v of ["Original", "Processed", "Heatmap", "Overlay", "Boxes"]) {
    await page.getByRole("tab", { name: v }).click();
    await expect(page.getByTestId("image-viewer").locator("img")).toBeVisible();
  }
  await page.getByRole("button", { name: "Zoom in" }).click();
  await expect(page.getByText("150%")).toBeVisible();
});

test("6. a REVIEW inspection can be approved by a reviewer", async ({ page }) => {
  await login(page);
  await runDemoInspection(page, "Subtle defect", /Subtle defect → REVIEW/);
  await expect(page.getByTestId("decision")).toHaveText("REVIEW");
  await page.getByRole("link", { name: "Human Review" }).first().click();
  await expect(page.getByRole("heading", { name: "Human Review Queue" })).toBeVisible();
  await page.getByLabel(/reviewer comment/i).fill("Looks acceptable on closer inspection");
  await page.getByRole("button", { name: /approve product/i }).click();
  await expect(page.getByText(/Recorded: approve/)).toBeVisible();
});

test("7. a PDF report can be downloaded", async ({ page }) => {
  await login(page);
  await page.getByRole("link", { name: "Quality Reports" }).click();
  const first = page.getByRole("button", { name: /download report/i }).first();
  const [dl] = await Promise.all([page.waitForEvent("download"), first.click()]);
  expect(dl.suggestedFilename()).toMatch(/inspection-\d+\.pdf/);
});
