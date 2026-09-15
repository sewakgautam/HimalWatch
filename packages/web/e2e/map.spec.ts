import { expect, test } from "@playwright/test";

// Runs against the static export (see playwright.config.ts's webServer —
// `serve out`, not `next dev`), since that's the artifact that actually
// ships to Firebase Hosting.

test("map loads and renders the basemap canvas", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("canvas.maplibregl-canvas")).toBeVisible();
});

test("filter panel shows a count that matches the loaded dataset", async ({ page }) => {
  await page.goto("/");
  const panel = page.getByText(/Filters · \d+ of \d+/);
  await expect(panel).toBeVisible();
  const text = await panel.textContent();
  const [, shown, total] = text!.match(/Filters · (\d+) of (\d+)/) ?? [];
  expect(Number(shown)).toBe(Number(total)); // no filter active yet -> counts match
  expect(Number(total)).toBeGreaterThan(0);
});

// MapLibre renders to a single WebGL canvas, and its own internal
// click-vs-drag hit-testing does not reliably respond to CDP-synthesized
// mouse/pointer input in headless Chromium — a well-documented limitation
// of browser-automating canvas-based map libraries, not something this
// app's code controls. Rather than fight that, this test drives the real
// registered handler through MapLibre's own public `fire()` API with a
// feature list built from the same `queryRenderedFeatures` call a real
// click would use — exercising every line of *our* code (the click
// handler, the id lookup against the live index, the onSelectFeature
// call, and the drawer's render) without depending on WebGL raycasting
// behaving a particular way under synthetic input.
test("clicking a glacier feature opens the detail drawer", async ({ page }) => {
  await page.goto("/");
  await page.waitForFunction(() => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const map = (window as any).__himalwatchMap;
    // Checking the layer's own existence, not map.isStyleLoaded() — that
    // also waits on the third-party basemap's own tiles to finish, which
    // is unrelated to whether our overlay layers are ready.
    return Boolean(map && map.getLayer("glaciers-fill"));
  });
  await page.waitForFunction(() => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const map = (window as any).__himalwatchMap;
    return Boolean(map.isSourceLoaded("glaciers"));
  });

  const fired = await page.evaluate(() => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const map = (window as any).__himalwatchMap;
    // One of the known dry-run glacier centroids — see
    // synthetic_dry_run_glaciers in the pipeline (base_lng=86.8,
    // base_lat=27.95, offset 0 for the first one).
    const point = map.project([86.8, 27.95]);
    const features = map.queryRenderedFeatures([point.x, point.y], {
      layers: ["glaciers-fill"],
    });
    if (features.length === 0) return false;
    map.fire("click", { lngLat: map.unproject(point), point, features });
    return true;
  });
  expect(fired).toBe(true);

  await expect(page.getByRole("button", { name: "Close" })).toBeVisible({ timeout: 5000 });
  await expect(page.getByText("Elevation").first()).toBeVisible();
});

test("changing a filter updates the URL", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("checkbox", { name: "koshi", exact: true }).check();
  await expect(page).toHaveURL(/basin=koshi/);
});

test("reloading the page preserves filter state from the URL", async ({ page }) => {
  await page.goto("/?basin=koshi");
  const checkbox = page.getByRole("checkbox", { name: "koshi", exact: true });
  await expect(checkbox).toBeChecked();

  await page.reload();
  await expect(checkbox).toBeChecked();
  await expect(page).toHaveURL(/basin=koshi/);
});
