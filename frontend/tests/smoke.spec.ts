import { expect, test } from "@playwright/test";

const validPng = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGNUCKhgYGBgYmBgYGBgAAAKsgDsz7n2agAAAABJRU5ErkJggg==",
  "base64",
);

test("real image investigation journey or honest backend-unavailable state", async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: /media evidence review for ai-generated or altered content/i }),
  ).toBeVisible();

  await page.locator("#image-file").setInputFiles({
    name: "smoke-sample.png",
    mimeType: "image/png",
    buffer: validPng,
  });
  await expect(page.getByRole("img", { name: /preview of smoke-sample\.png/i })).toBeVisible();
  const analysisResponsePromise = page
    .waitForResponse(
      (response) =>
        response.url().includes("/api/analyze") && response.url().endsWith("/api/analyze"),
      { timeout: 10_000 },
    )
    .catch(() => null);
  const eventsResponsePromise = page.waitForResponse((response) => {
    return response.url().includes("/api/analyze/") && response.url().endsWith("/events");
  }, { timeout: 20_000 }).catch(() => null);
  await page.getByRole("button", { name: "Run forensic review" }).click();
  const analysisResponse = await analysisResponsePromise;
  if (!analysisResponse || !analysisResponse.ok()) {
    await expect(page.locator("form [role='alert']")).toContainText(
      /could not be reached|unavailable|failed|try again/i,
    );
    return;
  }
  const eventsResponse = await eventsResponsePromise;
  if (!eventsResponse) throw new Error("The backend did not expose the image investigation events.");
  expect(eventsResponse.ok()).toBeTruthy();
  expect(await eventsResponse.text()).toContain("run_detector_ensemble");

  const backendUnavailable = page.locator("form [role='alert']");
  const resultHeading = page.getByRole("heading", { name: /investigation summary/i });
  await expect(backendUnavailable.or(resultHeading)).toBeVisible({ timeout: 240_000 });

  if (await resultHeading.isVisible().catch(() => false)) {
    await expect(page.getByRole("heading", { name: /likely ai|inconclusive|no ai signs found/i })).toBeVisible();
    const telugu = page.getByRole("button", { name: "TE", exact: true });
    await telugu.click();
    await expect(telugu).toHaveAttribute("aria-pressed", "true");
    await page.getByRole("button", { name: "EN", exact: true }).click();
    await page.getByRole("button", { name: "Detailed", exact: true }).click();
    await page.getByText("Under the hood", { exact: true }).click();
    await expect(
      page.locator("summary").filter({ hasText: /run_detector_ensemble/ }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Copy result link" }).click();
    await expect(page.getByRole("status").filter({ hasText: /result link copied/i })).toBeVisible();
    const [shareCardResponse, shareCardDownload] = await Promise.all([
      page.waitForResponse((response) => response.url().includes("/share-card.png")),
      page.waitForEvent("download"),
      page.getByRole("button", { name: "Download share card" }).click(),
    ]);
    expect(shareCardResponse.ok()).toBeTruthy();
    expect(shareCardResponse.headers()["content-type"]).toContain("image/png");
    expect(shareCardDownload.suggestedFilename()).toBe("very-frame-result.png");
  } else {
    await expect(backendUnavailable).toContainText(/could not be reached|unavailable|try again/i);
    await expect(page).toHaveURL(/\/$/);
  }
});

test("mobile layout supports keyboard-triggered image selection without horizontal overflow", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  const chooseImage = page.getByRole("button", { name: "Choose image" });
  await expect(chooseImage).toBeVisible();
  await expect(page.getByText("Take a photo", { exact: true })).toBeVisible();

  const chooserPromise = page.waitForEvent("filechooser");
  await chooseImage.focus();
  await page.keyboard.press("Enter");
  const chooser = await chooserPromise;
  await chooser.setFiles({
    name: "keyboard-selection.png",
    mimeType: "image/png",
    buffer: validPng,
  });
  await expect(page.getByRole("img", { name: /preview of keyboard-selection\.png/i })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});

test("video picker previews the selection and reports unavailable backend support honestly", async ({
  page,
}) => {
  await page.route("**/api/video/config", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        available: false,
        formats: [],
        max_size_mb: 100,
        max_duration_seconds: 600,
        max_resolution: "1920x1080",
        max_fps: 60,
        max_analyzed_frames: 24,
        analysis_timeout_seconds: 300,
        message: "Video analysis requires FFmpeg and ffprobe on the backend PATH.",
      }),
    }),
  );
  await page.goto("/");
  await page.locator("#video-file").setInputFiles({
    name: "sample.mp4",
    mimeType: "video/mp4",
    buffer: Buffer.from("not-a-decodable-video"),
  });

  await expect(page.locator('video[aria-label="Video preview: sample.mp4"]')).toBeVisible();
  await expect(page.locator("p").filter({ hasText: "sample.mp4" }).first()).toBeVisible();
  await expect(page.locator("#video-camera-file")).toHaveAttribute("capture", "environment");
  await expect(page.locator("form [role='alert']").first()).toContainText(
    /FFmpeg and ffprobe|metadata could not be read/i,
  );
  await expect(page.getByRole("button", { name: "Run video investigation" })).toBeDisabled();
});

test("PWA shell registers and sample gallery does not fabricate assets", async ({ page }) => {
  await page.route("**/api/samples", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ samples: [] }),
    }),
  );
  const manifestResponse = await page.request.get("/manifest.webmanifest");
  expect(manifestResponse.ok()).toBeTruthy();
  const manifest = await manifestResponse.json();
  expect(manifest.name).toBe("Very Frame AI");
  expect(manifest.icons).toHaveLength(1);

  await page.goto("/");
  await expect
    .poll(() =>
      page.evaluate(async () => Boolean(await navigator.serviceWorker.getRegistration("/"))),
    )
    .toBeTruthy();

  await page.goto("/samples");
  await expect(page.getByText(/No demo media or ground-truth labels have been fabricated/i)).toBeVisible();
});
