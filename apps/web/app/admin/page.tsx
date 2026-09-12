"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";

type Admin = { username: string; role: string; service_activation_enabled: boolean };
type Overview = { orders_today: number; processing_orders: number; completed_orders: number; failed_orders: number; failed_jobs: number; failed_deliveries: number; wallet_topups_today: number; failed_payments: number; backup: { status: "ok" | "missing" | "stale" | "unconfigured"; last_success_at: string | null } };
type Order = { id: string; status: string; channel: string; service_name: string; price_snapshot_halalas: number; currency: string; created_at: string; failed_jobs: number };
type FailedWork = { id: string; order_id: string; service_name: string; error_code: string | null; attempt_count: number; max_attempts: number; failed_at: string | null };
type FailedPayment = { id: string; provider: string; amount_halalas: number; created_at: string };
type Attention = { jobs: FailedWork[]; deliveries: FailedWork[]; payments: FailedPayment[] };
type Service = { id: string; slug: string; name_ar: string; description_ar: string; category_name_ar: string; processor_type: string; base_price_halalas: number; enabled: boolean; revision: number };
type Category = { id: string; slug: string; name_ar: string; enabled: boolean };

const currency = (halalas: number) => new Intl.NumberFormat("ar-SA", { style: "currency", currency: "SAR" }).format(halalas / 100);
const halalasFromInput = (amount: string): number | null => {
  if (!/^(?:0|[1-9]\d{0,4})(?:\.\d{1,2})?$/.test(amount)) return null;
  const [riyals, fraction = ""] = amount.split(".");
  const value = Number(riyals) * 100 + Number(fraction.padEnd(2, "0"));
  return value <= 1_000_000 ? value : null;
};

export default function AdminPage() {
  const [admin, setAdmin] = useState<Admin | null>(null);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [orders, setOrders] = useState<Order[]>([]);
  const [attention, setAttention] = useState<Attention | null>(null);
  const [services, setServices] = useState<Service[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    try {
      const me = await fetch("/api/admin/me", { credentials: "same-origin", cache: "no-store" });
      if (me.status === 401) { setAdmin(null); setOverview(null); setAttention(null); setOrders([]); setServices([]); setCategories([]); return; }
      if (!me.ok) throw new Error("تعذر التحقق من صلاحيات الإدارة");
      const person: Admin = await me.json();
      const [stats, list, incidents, catalog, groups] = await Promise.all([
        fetch("/api/admin/overview", { cache: "no-store" }),
        fetch("/api/admin/orders", { cache: "no-store" }),
        fetch("/api/admin/attention", { cache: "no-store" }),
        fetch("/api/admin/services", { cache: "no-store" }),
        fetch("/api/admin/categories", { cache: "no-store" }),
      ]);
      if (!stats.ok || !list.ok || !incidents.ok || !catalog.ok || !groups.ok) throw new Error("تعذر تحميل بيانات التشغيل");
      setAdmin(person);
      setOverview(await stats.json());
      setOrders(await list.json());
      setAttention(await incidents.json());
      setServices(await catalog.json());
      setCategories(await groups.json());
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "حدث خطأ غير متوقع");
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  async function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      const result = await fetch("/api/admin/login", {
        method: "POST", headers: { "Content-Type": "application/json" },
        credentials: "same-origin", body: JSON.stringify({ username: form.get("username"), password: form.get("password") }),
      });
      if (!result.ok) throw new Error(result.status === 429 ? "محاولات كثيرة، حاول بعد 15 دقيقة" : "تعذر تسجيل الدخول، تحقق من البيانات");
      await refresh();
    } catch (e) { setError(e instanceof Error ? e.message : "تعذر تسجيل الدخول"); }
  }

  async function signOut() {
    const result = await fetch("/api/admin/logout", { method: "POST", credentials: "same-origin" });
    if (result.ok) { setAdmin(null); setOverview(null); setAttention(null); setOrders([]); setServices([]); setCategories([]); }
    else setError("تعذر تسجيل الخروج");
  }

  async function saveService(event: FormEvent<HTMLFormElement>, service: Service) {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    const price = halalasFromInput(String(fields.get("price") ?? ""));
    if (price === null) { setError("السعر يجب أن يكون بين 0 و10,000 ريال، بدقة هللتين"); return; }
    const enabled = fields.get("enabled") === null ? service.enabled : fields.get("enabled") === "true";
    if (enabled !== service.enabled && !window.confirm(`تأكيد ${enabled ? "تفعيل" : "إيقاف"} خدمة ${service.name_ar}؟`)) return;
    try {
      const result = await fetch(`/api/admin/services/${service.id}`, {
        method: "PATCH", credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expected_revision: service.revision, reason: fields.get("reason"),
          description_ar: fields.get("description"), base_price_halalas: price, enabled,
          confirm: enabled !== service.enabled }),
      });
      if (!result.ok) {
        if (result.status === 409) { await refresh(); throw new Error("تغيّرت الخدمة من جلسة أخرى، راجع البيانات ثم أعد الحفظ"); }
        throw new Error(result.status === 403 ? "ليس لديك صلاحية تعديل الخدمات" :
          result.status === 422 ? "التعديل غير مقبول؛ تحقق من السبب وحالة التفعيل" : "تعذر حفظ الخدمة");
      }
      const updated = await result.json();
      setServices(previous => previous.map(item => item.id === service.id ? { ...item, ...updated } : item));
      setError("");
    } catch (e) { setError(e instanceof Error ? e.message : "تعذر حفظ الخدمة"); }
  }

  async function addCategory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const fields = new FormData(form);
    try {
      const result = await fetch("/api/admin/categories", {
        method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ slug: fields.get("slug"), name_ar: fields.get("name_ar"), reason: fields.get("reason") }),
      });
      if (!result.ok) throw new Error(result.status === 409 ? "الاسم المختصر مستخدم لتصنيف مختلف" : "تعذر إنشاء التصنيف، تحقق من البيانات");
      form.reset();
      await refresh();
    } catch (e) { setError(e instanceof Error ? e.message : "تعذر إنشاء التصنيف"); }
  }

  async function addService(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const fields = new FormData(form);
    const price = halalasFromInput(String(fields.get("price") ?? ""));
    if (price === null) { setError("السعر يجب أن يكون بين 0 و10,000 ريال، بدقة هللتين"); return; }
    let schema: unknown;
    try { schema = JSON.parse(String(fields.get("input_schema") ?? "{}")); }
    catch { setError("صيغة حقول الخدمة غير صحيحة"); return; }
    if (!schema || typeof schema !== "object" || Array.isArray(schema)) {
      setError("حقول الخدمة يجب أن تكون كائن JSON"); return;
    }
    try {
      const result = await fetch("/api/admin/services", {
        method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ category_id: fields.get("category_id"), slug: fields.get("slug"),
          name_ar: fields.get("name_ar"), description_ar: fields.get("description_ar"),
          processor_type: fields.get("processor_type"), base_price_halalas: price,
          input_schema: schema, reason: fields.get("reason") }),
      });
      if (!result.ok) throw new Error(result.status === 409 ? "الاسم المختصر مستخدم لخدمة مختلفة" :
        result.status === 404 ? "التصنيف غير موجود؛ حدّث الصفحة" : "تعذر تسجيل الخدمة، تحقق من المدخلات");
      form.reset();
      await refresh();
    } catch (e) { setError(e instanceof Error ? e.message : "تعذر تسجيل الخدمة"); }
  }

  const card = { border: "1px solid #d9e3e5", borderRadius: 14, padding: 20, background: "white" };
  if (loading) return <main><p>جارٍ تحميل لوحة التشغيل…</p></main>;
  if (!admin) return <main style={{ maxWidth: 410, margin: "10vh auto" }}>
    <h1>لوحة التشغيل</h1><p>سجّل الدخول للاطلاع على الطلبات وحالة التنفيذ.</p>
    <form onSubmit={signIn} style={{ ...card, display: "grid", gap: 14 }}>
      <label>اسم المستخدم<br /><input name="username" required autoComplete="username" style={{ width: "100%", padding: 10, boxSizing: "border-box" }} /></label>
      <label>كلمة المرور<br /><input name="password" type="password" required autoComplete="current-password" style={{ width: "100%", padding: 10, boxSizing: "border-box" }} /></label>
      <button type="submit" style={{ padding: 12, background: "#11484c", color: "white", border: 0, borderRadius: 8 }}>دخول</button>
    </form>{error && <p role="alert">{error}</p>}
  </main>;

  const metrics: [string, number][] = overview ? [
    ["طلبات اليوم", overview.orders_today], ["قيد التنفيذ", overview.processing_orders],
    ["مكتملة", overview.completed_orders], ["طلبات فاشلة", overview.failed_orders],
    ["شحن المحفظة اليوم", overview.wallet_topups_today],
  ] : [];
  const backup = overview?.backup;
  const backupLabel = backup?.status === "ok" ? "سليمة" : backup?.status === "stale" ? "متأخرة" : backup?.status === "missing" ? "لم تُنشأ بعد" : "غير مهيأة";
  const failures = [
    ...(attention?.jobs.map(item => ({ ...item, type: "مهمة" })) ?? []),
    ...(attention?.deliveries.map(item => ({ ...item, type: "تسليم" })) ?? []),
  ];
  return <main style={{ maxWidth: 1200, margin: "auto" }}>
    <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
      <div><h1>لوحة التشغيل</h1><p>مرحبًا {admin.username} · {admin.role}</p></div>
      <button onClick={signOut} style={{ padding: 10 }}>تسجيل الخروج</button>
    </header>
    {error && <p role="alert">{error}</p>}
    <section aria-label="مؤشرات التشغيل" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(190px,1fr))", gap: 12, marginBottom: 24 }}>
      {metrics.map(([label, value]) => <div key={label} style={card}><div>{label}</div><strong style={{ fontSize: 28 }}>{value}</strong></div>)}
    </section>
    <section style={{ ...card, marginBottom: 24, borderColor: "#bf8738" }}>
      <h2>تحتاج متابعة</h2><p>مهام فاشلة: {overview?.failed_jobs ?? 0} · تسليمات فاشلة: {overview?.failed_deliveries ?? 0} · طلبات فاشلة: {overview?.failed_orders ?? 0} · دفعات فاشلة: {overview?.failed_payments ?? 0}</p>
      <p role={backup?.status === "ok" ? undefined : "alert"}>النسخ الاحتياطي: {backupLabel}{backup?.last_success_at ? ` · آخر نسخة: ${new Date(backup.last_success_at).toLocaleString("ar-SA")}` : ""}</p>
      {failures.length > 0 && <><h3>المهام والتسليمات</h3><ul style={{ paddingInlineStart: 22 }}>
        {failures.map(item => <li key={`${item.type}-${item.id}`} style={{ paddingBlock: 8, overflowWrap: "anywhere" }}>
          <strong>{item.type} فاشل · {item.service_name}</strong> · الطلب <code dir="ltr">{item.order_id}</code>
          <br />رمز الخطأ: <code dir="ltr">{item.error_code ?? "UNKNOWN"}</code> · المحاولات: {item.attempt_count}/{item.max_attempts}
          {item.failed_at && <> · {new Date(item.failed_at).toLocaleString("ar-SA")}</>}
        </li>)}
      </ul></>}
      {(attention?.payments.length ?? 0) > 0 && <><h3>دفعات فاشلة</h3><ul style={{ paddingInlineStart: 22 }}>
        {attention?.payments.map(item => <li key={item.id} style={{ paddingBlock: 8, overflowWrap: "anywhere" }}>
          <strong>{item.provider}</strong> · {currency(item.amount_halalas)} · العملية <code dir="ltr">{item.id}</code>
          {" · "}{new Date(item.created_at).toLocaleString("ar-SA")}
        </li>)}
      </ul></>}
    </section>
    <section style={{ ...card, marginBottom: 24 }} aria-label="كتالوج الخدمات">
      <h2>الخدمات</h2>
      {!admin.service_activation_enabled && <p>تفعيل الخدمات الجديدة مؤجل حتى اكتمال متطلبات الإطلاق. يمكنك مراجعة الأسعار والأوصاف وإيقاف خدمة مفعّلة.</p>}
      {admin.role === "OWNER" && <>
        <details style={{ marginBottom: 12 }}><summary style={{ cursor: "pointer" }}>إضافة تصنيف</summary>
          <form onSubmit={event => void addCategory(event)} style={{ display: "grid", gap: 10, maxWidth: 500, marginTop: 12 }}>
            <label>الاسم<br /><input name="name_ar" required minLength={2} maxLength={120} /></label>
            <label>الاسم المختصر بالإنجليزية<br /><input name="slug" required pattern="[a-z0-9]+(-[a-z0-9]+)*" maxLength={60} dir="ltr" /></label>
            <label>سبب الإضافة<br /><input name="reason" required minLength={10} maxLength={500} /></label>
            <button type="submit" style={{ width: "fit-content", padding: 10 }}>إضافة التصنيف</button>
          </form>
        </details>
        <details style={{ marginBottom: 16 }}><summary style={{ cursor: "pointer" }}>تسجيل خدمة جديدة (معطّلة افتراضيًا)</summary>
          <form onSubmit={event => void addService(event)} style={{ display: "grid", gap: 10, maxWidth: 500, marginTop: 12 }}>
            <label>التصنيف<br /><select name="category_id" required defaultValue="">
              <option value="" disabled>اختر التصنيف</option>
              {categories.filter(category => category.enabled).map(category => <option key={category.id} value={category.id}>{category.name_ar}</option>)}
            </select></label>
            <label>اسم الخدمة<br /><input name="name_ar" required minLength={2} maxLength={120} /></label>
            <label>الاسم المختصر بالإنجليزية<br /><input name="slug" required pattern="[a-z0-9]+(-[a-z0-9]+)*" maxLength={60} dir="ltr" /></label>
            <label>الوصف<br /><textarea name="description_ar" maxLength={1000} rows={3} /></label>
            <label>المعالج<br /><select name="processor_type" defaultValue="tool">
              <option value="tool">أداة</option><option value="ai">ذكاء اصطناعي</option><option value="template">قالب</option>
              <option value="manual">يدوي</option><option value="hybrid">مختلط</option>
            </select></label>
            <label>السعر بالريال<br /><input name="price" required inputMode="decimal" defaultValue="0.00" /></label>
            <label>حقول الخدمة (JSON)<br /><textarea name="input_schema" dir="ltr" defaultValue="{}" rows={3} maxLength={4000} style={{ width: "100%" }} /></label>
            <small>لأداة دمج PDF: {`{"min_files":2,"max_files":10,"file_mime":"application/pdf"}`}</small>
            <label>سبب الإضافة<br /><input name="reason" required minLength={10} maxLength={500} /></label>
            <button type="submit" disabled={!categories.some(category => category.enabled)} style={{ width: "fit-content", padding: 10 }}>تسجيل الخدمة</button>
          </form>
        </details>
      </>}
      {services.map(service => <details key={service.id} style={{ borderTop: "1px solid #e6ebed", paddingBlock: 12 }}>
        <summary style={{ cursor: "pointer" }}><strong>{service.name_ar}</strong> · {service.category_name_ar} · {currency(service.base_price_halalas)} · {service.enabled ? "مفعّلة" : "معطّلة"}</summary>
        <p dir="ltr" style={{ textAlign: "right" }}>{service.slug} · {service.processor_type} · revision {service.revision}</p>
        {admin.role === "OWNER" ? <form key={service.revision} onSubmit={event => void saveService(event, service)} style={{ display: "grid", gap: 10, maxWidth: 500 }}>
          <label>الوصف<br /><textarea name="description" defaultValue={service.description_ar} maxLength={1000} rows={3} style={{ width: "100%" }} /></label>
          <label>السعر بالريال<br /><input name="price" type="text" inputMode="decimal" required defaultValue={(service.base_price_halalas / 100).toFixed(2)} /></label>
          <label>الإتاحة<br /><select name="enabled" defaultValue={String(service.enabled)} disabled={!service.enabled && !admin.service_activation_enabled}>
            <option value="false">معطّلة</option><option value="true">مفعّلة</option>
          </select></label>
          <label>سبب التعديل<br /><input name="reason" required minLength={10} maxLength={500} style={{ width: "100%" }} /></label>
          <button type="submit" style={{ width: "fit-content", padding: 10 }}>حفظ التعديل</button>
        </form> : <p>{service.description_ar || "لا يوجد وصف."}</p>}
      </details>)}
      {!services.length && <p>لا توجد خدمات مسجلة بعد.</p>}
    </section>
    <section style={card}><h2>آخر الطلبات</h2><div style={{ overflowX: "auto" }}><table style={{ width: "100%", borderCollapse: "collapse", textAlign: "right" }}>
      <thead><tr><th>الطلب</th><th>الخدمة</th><th>الحالة</th><th>القيمة</th><th>التاريخ</th></tr></thead>
      <tbody>{orders.map(order => <tr key={order.id} style={{ borderTop: "1px solid #e6ebed" }}>
        <td style={{ padding: 12 }} dir="ltr">{order.id.slice(0, 8)}</td><td>{order.service_name}</td><td>{order.status}{order.failed_jobs > 0 ? " · مهمة فاشلة" : ""}</td>
        <td>{currency(order.price_snapshot_halalas)}</td><td>{new Date(order.created_at).toLocaleString("ar-SA")}</td>
      </tr>)}</tbody></table>{!orders.length && <p>لا توجد طلبات بعد.</p>}</div></section>
  </main>;
}
