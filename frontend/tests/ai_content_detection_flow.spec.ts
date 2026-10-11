import { expect, test } from "@playwright/test";

test("AI-Generated Content Detection Card renders on image result page", async ({ page }) => {
  await page.goto("/result/q_P93RO8DJT6QBpGCjBNzA");
  
  // Verify AI Content Detection Results section is visible
  await expect(page.getByRole("heading", { name: "AI Content Detection Results" })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("Likely AI-Generated").first()).toBeVisible();
  await expect(page.getByText("AI-Generated Probability").first()).toBeVisible();
  await expect(page.getByText("Likely Human-Created").first()).toBeVisible();
  await expect(page.getByText("88.0%").first()).toBeVisible();
  await expect(page.getByText("12.0%").first()).toBeVisible();

  // Verify Download Dossier link is present
  const dossierLink = page.getByRole("link", { name: /dossier/i });
  await expect(dossierLink.first()).toBeVisible();
});

test("AI-Generated Content Detection Card and Video Player render on video result page", async ({ page }) => {
  await page.goto("/video/result/oX8WFMiOMIfu8jEed80x6Q");
  
  // Verify AI Content Detection Results section is visible on video page
  await expect(page.getByRole("heading", { name: "AI Content Detection Results" })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("AI-Generated Probability").first()).toBeVisible();
  await expect(page.getByText("78.5%").first()).toBeVisible();
  await expect(page.getByText("21.5%").first()).toBeVisible();
  await expect(page.getByText(/Frames Analyzed/i).first()).toBeVisible();

  // Verify Nemotron or Multimodal section is present
  await expect(page.getByText(/nemotron|multimodal/i).first()).toBeVisible();
});

test("Case Workspace loads and displays case information", async ({ page }) => {
  await page.goto("/cases/CASE-202610-DEMO01");
  
  // Verify case title and items load without errors
  await expect(page.getByText("Viral Press Conference").first()).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("Dr. V. Rao").first()).toBeVisible();
});
