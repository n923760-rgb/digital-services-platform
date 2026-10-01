const assert = require("node:assert/strict");
const { chromium } = require("playwright-core");

const base = process.env.DSP_BROWSER_URL || "http://127.0.0.1:3100";
const timestamp = "2026-10-01T12:00:00Z";
const long = "اسمخدمةعربيةطويلةبدونمسافات".repeat(5);
const id = "00000000-0000-4000-8000-000000000001";
const fixture = {
  me: { username: "test-owner", role: "OWNER", service_activation_enabled: false },
  overview: { orders_today: 1, processing_orders: 0, completed_orders: 1, failed_orders: 0,
    failed_jobs: 0, failed_deliveries: 0, new_custom_requests: 1, reviewing_custom_requests: 0,
    wallet_topups_today: 0, failed_payments: 0, backup: { status: "ok", last_success_at: timestamp } },
  orders: [{ id, status: "COMPLETED", channel: "TELEGRAM", service_name: long,
    price_snapshot_halalas: 1250, currency: "SAR", created_at: timestamp, failed_jobs: 0 }],
  attention: { jobs: [], deliveries: [], payments: [] },
  services: [{ id, slug: "pdf-merge", name_ar: long, description_ar: long, category_name_ar: long,
    processor_type: "tool", base_price_halalas: 1250, enabled: false, revision: 1 }],
  categories: [{ id, slug: "files", name_ar: long, enabled: true }],
  "custom-requests": [{ id, description: long, status: "NEW", revision: 1,
    reviewer_username: null, telegram_user_id: 12345, created_at: timestamp, updated_at: timestamp }],
};

function gate() {
  let release;
  const promise = new Promise(resolve => { release = resolve; });
  return { promise, release };
}

async function open(browser, { authenticated = true, role = "OWNER" } = {}) {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  const state = { authenticated, role, loginCount: 0, logoutCount: 0, logoutFails: false,
    loginGate: null, overviewGate: null };
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.route("**/api/admin/**", async route => {
    const endpoint = new URL(route.request().url()).pathname.replace("/api/admin/", "");
    if (endpoint === "login") {
      state.loginCount++;
      if (state.loginGate) await state.loginGate.promise;
      state.authenticated = true;
      return route.fulfill({ json: { ok: true } });
    }
    if (endpoint === "logout") {
      state.logoutCount++;
      if (state.logoutFails) return route.abort("failed");
      state.authenticated = false;
      return route.fulfill({ json: { ok: true } });
    }
    if (endpoint === "me") return route.fulfill({ status: state.authenticated ? 200 : 401,
      json: { ...fixture.me, role: state.role } });
    if (route.request().method() === "PATCH") return route.fulfill({ json: { ok: true } });
    if (endpoint === "overview" && state.overviewGate) await state.overviewGate.promise;
    if (!(endpoint in fixture)) throw new Error("Unhandled mocked endpoint: " + endpoint);
    return route.fulfill({ json: fixture[endpoint] });
  });
  await page.goto(base + "/admin");
  await page.getByRole("heading", { name: "لوحة التشغيل", exact: true }).waitFor();
  return { page, context, state, errors };
}

async function noOverflow(page, label) {
  const sizes = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    content: document.documentElement.scrollWidth,
  }));
  assert.ok(sizes.content <= sizes.viewport, label + ": " + JSON.stringify(sizes));
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const { page, context, errors } = await open(browser);
    await page.locator("details").evaluateAll(items => items.forEach(item => { item.open = true; }));
    assert.equal(await page.locator("html").getAttribute("dir"), "rtl");
    await page.getByLabel("سبب بدء المراجعة", { exact: true }).fill("سبب اختبار موثق فقط");
    for (const width of [320, 360, 390, 1280]) {
      await page.setViewportSize({ width, height: 900 });
      await noOverflow(page, "OWNER " + width);
      const badControls = await page.locator("input,select,textarea").evaluateAll(items =>
        items.filter(item => item.getBoundingClientRect().width > item.closest("form").getBoundingClientRect().width).length);
      assert.equal(badControls, 0);
      console.log("PASS RTL long Arabic/open forms viewport " + width);
    }
    // Doubled text size is a reflow check, not a claim of native browser zoom or screen-reader testing.
    await page.setViewportSize({ width: 320, height: 900 });
    await page.addStyleTag({ content: "body { font-size: 200%; }" });
    await noOverflow(page, "200% text reflow");
    const region = page.getByRole("region", { name: "جدول آخر الطلبات" });
    await region.focus();
    assert.equal(await region.evaluate(el => el === document.activeElement), true);
    assert.notEqual(await region.evaluate(el => getComputedStyle(el).outlineStyle), "none");
    await page.keyboard.press("ArrowLeft");
    assert.equal(await page.locator('th[scope="col"]').count(), 5);
    assert.deepEqual(errors, []);
    await context.close();

    const operator = await open(browser, { role: "OPERATOR" });
    await operator.page.setViewportSize({ width: 320, height: 900 });
    await noOverflow(operator.page, "OPERATOR");
    assert.equal(await operator.page.getByLabel("سبب بدء المراجعة").count(), 0);
    assert.equal(await operator.page.getByRole("button", { name: "حفظ التعديل" }).count(), 0);
    await operator.context.close();
    console.log("PASS operator read-only UI and table keyboard focus");

    const login = await open(browser, { authenticated: false });
    await login.page.setViewportSize({ width: 320, height: 900 });
    await noOverflow(login.page, "login");
    await login.page.getByLabel("اسم المستخدم", { exact: true }).fill("test-owner");
    await login.page.getByLabel("كلمة المرور", { exact: true }).fill("synthetic-fixture-only");
    login.state.loginGate = gate();
    await login.page.locator("form").evaluate(form => {
      form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
      form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    });
    await login.page.getByRole("button", { name: "جارٍ الدخول…" }).waitFor();
    assert.equal(await login.page.getByRole("button", { name: "جارٍ الدخول…" }).isDisabled(), true);
    login.state.loginGate.release();
    await login.page.getByRole("button", { name: "تسجيل الخروج", exact: true }).waitFor();
    assert.equal(login.state.loginCount, 1);
    login.state.logoutFails = true;
    await login.page.getByRole("button", { name: "تسجيل الخروج", exact: true }).click();
    await login.page.getByRole("alert").filter({ hasText: "تعذر تسجيل الخروج" }).waitFor();
    await login.page.getByRole("button", { name: "تسجيل الخروج", exact: true }).waitFor();
    login.state.logoutFails = false;
    // Start a refresh through a real triage form, then resolve its data after logout.
    login.state.overviewGate = gate();
    await login.page.getByLabel("سبب بدء المراجعة", { exact: true }).fill("سبب اختبار موثق فقط");
    const overviewStarted = login.page.waitForRequest("**/api/admin/overview");
    await login.page.getByRole("button", { name: "بدء المراجعة", exact: true }).click();
    await overviewStarted;
    await login.page.getByRole("button", { name: "تسجيل الخروج", exact: true }).click();
    await login.page.getByLabel("كلمة المرور", { exact: true }).waitFor();
    const lateResponse = login.page.waitForResponse("**/api/admin/overview");
    login.state.overviewGate.release();
    await lateResponse;
    await login.page.waitForFunction(() => !document.querySelector('button[aria-busy="true"]'));
    assert.equal(await login.page.getByRole("button", { name: "تسجيل الخروج", exact: true }).count(), 0);
    assert.equal(await login.page.getByLabel("كلمة المرور", { exact: true }).count(), 1);
    assert.deepEqual(login.errors, []);
    await login.context.close();
    console.log("PASS duplicate login guard, failed logout recovery and stale refresh after logout");
    console.log("Admin browser checks PASS (built Next.js + mocked admin API; no production/Telegram claim)");
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
