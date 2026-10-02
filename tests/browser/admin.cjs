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
    wallet_topups_today: 0, failed_payments: 0, pending_star_refunds: 2, pending_star_receipts: 1, backup: { status: "ok", last_success_at: timestamp } },
  orders: [{ id, status: "COMPLETED", channel: "TELEGRAM", service_name: long,
    price_snapshot_halalas: 1250, currency: "SAR", created_at: timestamp, failed_jobs: 0 },
    { id: "00000000-0000-4000-8000-000000000002", status: "COMPLETED", channel: "telegram",
      service_name: long, price_snapshot_halalas: 0, price_snapshot_stars: 37, currency: "XTR",
      created_at: timestamp, failed_jobs: 0 }],
  attention: { jobs: [], deliveries: [], payments: [] },
  services: [{ id, slug: "pdf-merge", name_ar: long, description_ar: long, category_name_ar: long,
    processor_type: "tool", processor_key: "summarize-text", base_price_halalas: 1250, base_price_stars: 37, enabled: false, revision: 1 }],
  categories: [{ id, slug: "files", name_ar: long, enabled: true }],
  "custom-requests": [{ id, description: long, status: "NEW", revision: 1,
    reviewer_username: null, telegram_user_id: 12345, created_at: timestamp, updated_at: timestamp }],
};

function gate() {
  let release;
  const promise = new Promise(resolve => { release = resolve; });
  return { promise, release };
}

async function open(browser, { authenticated = true, role = "OWNER", paged = false } = {}) {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  const state = { authenticated, role, loginCount: 0, logoutCount: 0, logoutFails: false,
    loginGate: null, overviewGate: null, pageGate: null, pageFails: false, pageUnauthorized: false, olderCount: 0, cursors: [], serviceWrites: [], productCreates: [], productGate: null,
    services: fixture.services.map(item => ({ ...item })) };
  const firstPage = Array.from({ length: 50 }, (_, index) => ({
    ...fixture["custom-requests"][0], id: "00000000-0000-4000-8000-" + String(50 - index).padStart(12, "0"),
    updated_at: "2026-10-01T12:00:00.123456Z",
  }));
  const oldRequest = { ...fixture["custom-requests"][0],
    id: "00000000-0000-4000-8000-000000000099", description: "طلب قديم خارج أحدث خمسين" };
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
    if (endpoint === "custom-requests" && paged) {
      const params = new URL(route.request().url()).searchParams;
      if (!params.has("before_id")) return route.fulfill({ json: firstPage });
      state.olderCount++; state.cursors.push(Object.fromEntries(params));
      if (state.pageUnauthorized) return route.fulfill({ status: 401, json: { detail: "expired session" } });
      if (state.pageFails) return route.fulfill({ status: 503, json: { detail: "synthetic outage" } });
      if (state.pageGate) await state.pageGate.promise;
      return route.fulfill({ json: [oldRequest] });
    }
    if (endpoint === "me") return route.fulfill({ status: state.authenticated ? 200 : 401,
      json: { ...fixture.me, role: state.role } });
    if (endpoint === "services" && route.request().method() === "POST") {
      const body = route.request().postDataJSON();
      state.productCreates.push(body);
      if (state.productGate) await state.productGate.promise;
      const productId = "00000000-0000-4000-8000-000000000044";
      state.services.push({ ...body, id: productId, category_name_ar: fixture.categories[0].name_ar,
        enabled: false, revision: 1 });
      return route.fulfill({ json: { id: productId, enabled: false } });
    }
    if (endpoint === "services") return route.fulfill({ json: state.services });
    if (endpoint.startsWith("services/") && route.request().method() === "PATCH") {
      const body = route.request().postDataJSON();
      state.serviceWrites.push(body);
      const editedId = endpoint.slice("services/".length);
      state.services = state.services.map(item => item.id === editedId ? { ...item, ...body, revision: body.expected_revision + 1 } : item);
      return route.fulfill({ json: { ...body, revision: body.expected_revision + 1 } });
    }
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
    const { page, context, errors, state } = await open(browser);
    await page.locator("details").evaluateAll(items => items.forEach(item => { item.open = true; }));
    assert.equal(await page.locator("html").getAttribute("dir"), "rtl");
    await page.getByLabel("سبب بدء المراجعة", { exact: true }).fill("سبب اختبار موثق فقط");
    for (const width of [320, 360, 390, 1280]) {
      await page.setViewportSize({ width, height: 900 });
      await noOverflow(page, "OWNER " + width);
      const badControls = await page.locator("input,select,textarea").evaluateAll(items =>
        items.filter(item => item.getBoundingClientRect().width > item.closest("form").getBoundingClientRect().width).length);
      assert.equal(badControls, 0);
      const unlabeled = await page.locator("input,select,textarea").evaluateAll(items =>
        items.filter(item => !item.labels?.length && !item.getAttribute("aria-label")).length);
      assert.equal(unlabeled, 0);
      const shortTargets = await page.locator("button,summary").evaluateAll(items =>
        items.filter(item => item.getBoundingClientRect().height < 44).length);
      assert.equal(shortTargets, 0);
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
    await page.locator("td").filter({ hasText: "37 ⭐" }).waitFor();
    const serviceForm = page.locator("form").filter({ has: page.getByRole("button", { name: "حفظ التعديل", exact: true }) });
    await serviceForm.getByLabel("السعر بالنجوم", { exact: true }).fill("37.5");
    await serviceForm.getByLabel("سبب التعديل", { exact: true }).fill("اختبار تحديث سعر النجوم فقط");
    await serviceForm.getByRole("button", { name: "حفظ التعديل", exact: true }).click();
    await page.getByRole("alert").filter({ hasText: "السعر بالنجوم يجب" }).waitFor();
    assert.equal(state.serviceWrites.length, 0);
    await serviceForm.getByLabel("السعر بالنجوم", { exact: true }).fill("41");
    const savedPrice = page.waitForResponse("**/api/admin/services/" + id);
    await serviceForm.getByRole("button", { name: "حفظ التعديل", exact: true }).click();
    await savedPrice;
    assert.equal(state.serviceWrites.length, 1);
    assert.equal(state.serviceWrites[0].base_price_stars, 41);
    assert.equal(state.serviceWrites[0].base_price_halalas, 1250);
    await page.getByText("41 ⭐", { exact: false }).first().waitFor();
    console.log("PASS native XTR order display and integer Stars editor; fractions rejected, SAR history preserved");
    const productForm = page.locator("form").filter({ has: page.getByRole("button", { name: "تسجيل الخدمة", exact: true }) });
    await productForm.getByLabel("التصنيف", { exact: true }).selectOption(id);
    await productForm.getByLabel("اسم الخدمة", { exact: true }).fill("خدمة تلخيص إضافية");
    await productForm.getByLabel("الاسم المختصر بالإنجليزية", { exact: true }).fill("new-summary-product");
    await productForm.getByLabel("طريقة التنفيذ", { exact: true }).selectOption("summarize-text");
    await productForm.getByLabel("السعر بالنجوم", { exact: true }).fill("19");
    await productForm.getByLabel("سبب الإضافة", { exact: true }).fill("إضافة منتج تجريبي من اللوحة");
    state.productGate = gate();
    await productForm.evaluate(form => {
      form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
      form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    });
    await page.getByRole("button", { name: "جارٍ تسجيل الخدمة…", exact: true }).waitFor();
    assert.equal(await page.getByRole("button", { name: "جارٍ تسجيل الخدمة…", exact: true }).isDisabled(), true);
    state.productGate.release();
    const added = page.locator("details").filter({ has: page.getByText("خدمة تلخيص إضافية", { exact: true }) });
    await added.waitFor();
    assert.equal(state.productCreates.length, 1);
    assert.deepEqual(state.productCreates[0].input_schema, { max_characters: 4000 });
    assert.equal(state.productCreates[0].processor_key, "summarize-text");
    assert.equal(state.productCreates[0].base_price_stars, 19);
    assert.equal("enabled" in state.productCreates[0], false);
    await added.evaluate(element => { element.open = true; });
    await added.getByLabel("اسم المنتج", { exact: true }).fill("تلخيص باسم محدّث");
    await added.getByLabel("السعر بالنجوم", { exact: true }).fill("23");
    await added.getByLabel("سبب التعديل", { exact: true }).fill("تعديل اسم وسعر المنتج لاحقًا");
    await added.getByRole("button", { name: "حفظ التعديل", exact: true }).click();
    await page.getByText("تلخيص باسم محدّث", { exact: true }).waitFor();
    assert.equal(state.serviceWrites.at(-1).base_price_stars, 23);
    assert.equal(state.serviceWrites.at(-1).name_ar, "تلخيص باسم محدّث");
    console.log("PASS product creation with known executor, duplicate-submit guard and later name/Stars-price edits");
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
    const response = await lateResponse;
    await response.finished();
    await login.page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    await login.page.waitForFunction(() => !document.querySelector('button[aria-busy="true"]'));
    assert.equal(await login.page.getByRole("button", { name: "تسجيل الخروج", exact: true }).count(), 0);
    assert.equal(await login.page.getByLabel("كلمة المرور", { exact: true }).count(), 1);
    assert.deepEqual(login.errors, []);
    await login.context.close();
    console.log("PASS duplicate login guard, failed logout recovery and stale refresh after logout");
    const pagination = await open(browser, { paged: true });
    const queue = pagination.page.getByRole("region", { name: "طلبات الخدمات الخاصة" });
    assert.equal(await queue.locator("article").count(), 50);
    pagination.state.pageFails = true;
    await pagination.page.getByRole("button", { name: "عرض طلبات أقدم", exact: true }).click();
    await pagination.page.getByRole("alert").filter({ hasText: "تعذر تحميل صفحة الطلبات" }).waitFor();
    assert.equal(await queue.locator("article").count(), 50);
    pagination.state.pageFails = false; pagination.state.pageGate = gate();
    await pagination.page.getByRole("button", { name: "عرض طلبات أقدم", exact: true }).evaluate(button => {
      button.click(); button.click();
    });
    await pagination.page.getByRole("status").filter({ hasText: "جارٍ تحميل صفحة الطلبات" }).waitFor();
    assert.equal(await pagination.page.getByRole("button", { name: "عرض طلبات أقدم", exact: true }).isDisabled(), true);
    pagination.state.pageGate.release();
    await pagination.page.getByText("طلب قديم خارج أحدث خمسين", { exact: true }).waitFor();
    assert.equal(pagination.state.olderCount, 2);
    assert.equal(await queue.locator("article").count(), 1);
    assert.equal(pagination.state.cursors[1].before_updated_at, "2026-10-01T12:00:00.123456Z");
    assert.equal(pagination.state.cursors[1].before_id, "00000000-0000-4000-8000-000000000001");
    await pagination.page.getByRole("button", { name: "العودة لأحدث الطلبات", exact: true }).click();
    await pagination.page.getByRole("button", { name: "عرض طلبات أقدم", exact: true }).waitFor();
    assert.equal(await queue.locator("article").count(), 50);
    pagination.state.pageGate = gate();
    const olderStarted = pagination.page.waitForRequest(request =>
      request.url().includes("custom-requests?"));
    await pagination.page.getByRole("button", { name: "عرض طلبات أقدم", exact: true }).click();
    await olderStarted;
    await pagination.page.getByRole("button", { name: "تسجيل الخروج", exact: true }).click();
    await pagination.page.getByLabel("كلمة المرور", { exact: true }).waitFor();
    const olderResponse = pagination.page.waitForResponse(response =>
      response.url().includes("custom-requests?"));
    pagination.state.pageGate.release();
    await (await olderResponse).finished();
    await pagination.page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    assert.equal(await pagination.page.getByText("طلب قديم خارج أحدث خمسين", { exact: true }).count(), 0);
    assert.equal(await pagination.page.getByLabel("كلمة المرور", { exact: true }).count(), 1);
    assert.deepEqual(pagination.errors, []);
    await pagination.context.close();
    const expiry = await open(browser, { paged: true });
    expiry.state.overviewGate = gate();
    await expiry.page.getByLabel("سبب بدء المراجعة", { exact: true }).first().fill("سبب اختبار موثق فقط");
    const expiryRefreshStarted = expiry.page.waitForRequest("**/api/admin/overview");
    await expiry.page.getByRole("button", { name: "بدء المراجعة", exact: true }).first().click();
    await expiryRefreshStarted;
    expiry.state.pageUnauthorized = true;
    await expiry.page.getByRole("button", { name: "عرض طلبات أقدم", exact: true }).click();
    await expiry.page.getByLabel("كلمة المرور", { exact: true }).waitFor();
    const expiredRefresh = expiry.page.waitForResponse("**/api/admin/overview");
    expiry.state.overviewGate.release();
    await (await expiredRefresh).finished();
    await expiry.page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    assert.equal(await expiry.page.getByLabel("كلمة المرور", { exact: true }).count(), 1);
    assert.equal(await expiry.page.getByRole("button", { name: "تسجيل الخروج", exact: true }).count(), 0);
    assert.deepEqual(expiry.errors, []);
    await expiry.context.close();
    console.log("PASS bounded pages/precision/retry/duplicate/late logout and expired-page stale-refresh guards");
    console.log("Admin browser checks PASS (built Next.js + mocked admin API; no production/Telegram claim)");
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
