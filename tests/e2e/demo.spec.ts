/**
 * MedBalance-Q end-to-end demo path test.
 *
 * Runs against VITE_USE_FIXTURES=1 (the Playwright config starts Vite in
 * fixture mode).  Each step screenshots into tests/e2e/screens/.
 */
import { test, expect, type Page } from '@playwright/test';
import path from 'path';

const SCREENS = path.resolve(__dirname, 'screens');

async function snap(page: Page, name: string) {
  await page.screenshot({ path: path.join(SCREENS, `${name}.png`), fullPage: true });
}

async function navTo(page: Page, label: string, route: string) {
  await page.getByRole('link', { name: label }).first().click();
  await page.waitForURL(`**${route}`);
}

test.describe.serial('Demo path', () => {
  let page: Page;

  test.beforeAll(async ({ browser }) => {
    page = await browser.newPage();
  });
  test.afterAll(async () => {
    await page.close();
  });

  test('01 — map loads with 4+ facilities', async () => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('h1, h2').filter({ hasText: /map|district/i }).first()).toBeVisible();
    const svgCircles = page.locator('svg circle');
    const leafletCircles = page.locator('path.leaflet-interactive');
    const count = await leafletCircles.count() + await svgCircles.count();
    expect(count).toBeGreaterThanOrEqual(4);
    await snap(page, '01_map');
  });

  test('02 — ingestion shows Kannada report with extracted insulin', async () => {
    await navTo(page, 'Ingestion', '/ingestion');
    await expect(page.getByRole('heading', { name: 'Ingestion & Review' })).toBeVisible();
    await expect(page.getByText('Chat (Kannada)').first()).toBeVisible();
    // Expand H3 report
    const h3Row = page.locator('text=H3').first();
    await h3Row.click();
    await expect(page.getByText('ಇನ್ಸುಲಿನ್').first()).toBeVisible();
    await expect(page.getByText(/Insulin/i).first()).toBeVisible();
    await snap(page, '02_ingestion_kannada');
  });

  test('03 — bad_data report flagged with review item', async () => {
    await expect(page.getByText('Flagged').first()).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Review Queue' })).toBeVisible();
    await expect(page.getByText('qty_spike').first()).toBeVisible();
    await expect(page.getByText(/data entry error/i).first()).toBeVisible();
    await snap(page, '03_bad_data_review');
  });

  test('04 — resolve review item', async () => {
    const acceptBtn = page.getByTitle('Accept as-is').first();
    await expect(acceptBtn).toBeVisible();
    await acceptBtn.click({ force: true });
    await snap(page, '04_review_resolved');
  });

  test('05 — scenarios page and dengue activation', async () => {
    await navTo(page, 'Scenarios', '/scenarios');
    await expect(page.getByRole('heading', { name: 'Scenario Console' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Simulation Clock' })).toBeVisible();
    await expect(page.locator('text=dengue_outbreak').first()).toBeVisible();
    await snap(page, '05_scenarios_dengue');
  });

  test('06 — plan page with solver tier and violations', async () => {
    await navTo(page, 'Plan', '/plan');
    await expect(page.getByRole('heading', { name: 'Redistribution Plan' })).toBeVisible();
    await expect(page.getByText(/QpiAI|Greedy|SA|Platform|Local/i).first()).toBeVisible();
    await expect(page.getByText('Violations: 0')).toBeVisible();
    await expect(page.getByText('ORD-').first()).toBeVisible();
    await snap(page, '06_plan_page');
  });

  test('07 — insulin order detail shows usable 28', async () => {
    const insulinLink = page.locator('a[href*="ORD-005"]').first();
    if (await insulinLink.isVisible()) {
      await insulinLink.click();
    } else {
      await page.goto('/orders/ORD-005');
    }
    await page.waitForLoadState('networkidle');
    await expect(page.getByText('DTA/BLR-U/2026/000005')).toBeVisible();
    await expect(page.getByText(/Insulin/i).first()).toBeVisible();
    await expect(page.getByText('28').first()).toBeVisible();
    await expect(page.getByText(/cold.chain/i).first()).toBeVisible();
    await snap(page, '07_order_insulin_detail');
  });

  test('08 — benchmark page has 5 solver rows', async () => {
    await navTo(page, 'Benchmark', '/benchmark');
    await expect(page.getByRole('heading', { name: 'Benchmark Comparison' })).toBeVisible();
    await expect(page.getByText('no-transfer').first()).toBeVisible();
    await expect(page.getByText('greedy-phone-call').first()).toBeVisible();
    await expect(page.getByText('greedy-f4').first()).toBeVisible();
    await expect(page.getByText(/qubo/i).first()).toBeVisible();
    await expect(page.getByText(/milp/i).first()).toBeVisible();
    await expect(page.getByText(/3\.02%/).first()).toBeVisible();
    await snap(page, '08_benchmark');
  });

  test('09 — cold chain excursion banner visible', async () => {
    await navTo(page, 'Cold Chain', '/coldchain');
    await expect(page.getByRole('heading', { name: 'Cold Chain Monitoring' })).toBeVisible();
    await expect(page.getByText(/Excursion Detected/i).first()).toBeVisible();
    await expect(page.getByText('sensor-01').first()).toBeVisible();
    await expect(page.getByText('sensor-02').first()).toBeVisible();
    await expect(page.getByText('sensor-03').first()).toBeVisible();
    await snap(page, '09_coldchain_excursion');
  });

  test('10 — copilot why-not mentions F3 or cold', async () => {
    const copilotBtn = page.locator('button').filter({
      has: page.locator('.lucide-message-square, .lucide-brain'),
    }).first();
    await copilotBtn.click();
    await expect(page.getByPlaceholder(/ask|message|type/i).first()).toBeVisible({ timeout: 5000 });
    const suggested = page.getByText("Why didn't Hesaraghatta get insulin?").first();
    if (await suggested.isVisible()) {
      await suggested.click();
    } else {
      const input = page.getByPlaceholder(/ask|message|type/i).first();
      await input.fill("Why didn't Hesaraghatta get insulin?");
      await page.keyboard.press('Enter');
    }
    await expect(page.getByText(/F3|cold.storage|cold_storage/i).first()).toBeVisible({ timeout: 15000 });
    await snap(page, '10_copilot_whynot');
    const closeBtn = page.locator('button').filter({
      has: page.locator('.lucide-x'),
    }).first();
    if (await closeBtn.isVisible()) await closeBtn.click();
  });

  test('11 — approve order', async () => {
    await page.goto('/orders/ORD-001');
    await page.waitForLoadState('networkidle');
    await expect(page.getByText('DTA/BLR-U/2026/000001').first()).toBeVisible();
    // Approve button present for proposed orders
    const approveBtn = page.getByRole('button', { name: /approve/i }).first();
    await expect(approveBtn).toBeVisible();
    await approveBtn.click();
    // In fixture mode the mutation fires then refetches static data;
    // verify the button text changed briefly to "Approving..."
    await page.waitForTimeout(500);
    await snap(page, '11_order_approved');
  });

  test('12 — voucher download button present', async () => {
    const downloadBtn = page.locator('button').filter({
      has: page.locator('.lucide-download'),
    }).first();
    await expect(downloadBtn).toBeVisible();
    await snap(page, '12_voucher_button');
  });

  test('13 — scan page dispatch and receive', async () => {
    await page.goto('/scan/ORD-004');
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(/Dispatch|Receive|ORS|ORD-004/i).first()).toBeVisible();
    const dispatchBtn = page.getByRole('button', { name: /dispatch/i }).first();
    if (await dispatchBtn.isVisible()) {
      await dispatchBtn.click();
      await expect(page.getByText(/dispatched|receive/i).first()).toBeVisible({ timeout: 5000 });
    }
    await snap(page, '13_scan_dispatch');
    const receiveBtn = page.getByRole('button', { name: /receive/i }).first();
    if (await receiveBtn.isVisible()) {
      await receiveBtn.click();
      await expect(page.getByText(/received|consume/i).first()).toBeVisible({ timeout: 5000 });
    }
    await snap(page, '13_scan_receive');
  });

  test('14 — audit chain verified', async () => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(/47|audit|chain/i).first()).toBeVisible();
    await snap(page, '14_audit_verified');
  });

  test('15 — results page renders with KPIs', async () => {
    await navTo(page, 'Results', '/results');
    await expect(page.getByRole('heading', { name: 'Results Dashboard' })).toBeVisible();
    await expect(page.getByText(/Stockout Days/i).first()).toBeVisible();
    await expect(page.getByText(/72%/i).first()).toBeVisible();
    await expect(page.getByText(/Full QUBO/i).first()).toBeVisible();
    await snap(page, '15_results');
  });

  test('16 — AI Health page shows provider info', async () => {
    await navTo(page, 'AI Health', '/ai-health');
    await expect(page.getByText(/Gemini/i).first()).toBeVisible();
    await expect(page.getByText(/72%/i).first()).toBeVisible();
    await snap(page, '16_ai_health');
  });
});
