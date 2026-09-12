"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";

type Admin = { username: string; role: string };
type Overview = { orders_today: number; processing_orders: number; completed_orders: number; failed_orders: number; failed_jobs: number; failed_deliveries: number; wallet_topups_today: number; failed_payments: number; backup: { status: "ok" | "missing" | "stale" | "unconfigured"; last_success_at: string | null } };
type Order = { id: string; status: string; channel: string; service_name: string; price_snapshot_halalas: number; currency: string; created_at: string; failed_jobs: number };

const currency = (halalas: number) => new Intl.NumberFormat("ar-SA", { style: "currency", currency: "SAR" }).format(halalas / 100);

export default function AdminPage() {
  const [admin, setAdmin] = useState<Admin | null>(null);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    try {
      const me = await fetch("/api/admin/me", { credentials: "same-origin", cache: "no-store" });
      if (me.status === 401) { setAdmin(null); setOverview(null); return; }
      if (!me.ok) throw new Error("تعذر التحقق من صلاحيات الإدارة");
      const person: Admin = await me.json();
      const [stats, list] = await Promise.all([
        fetch("/api/admin/overview", { cache: "no-store" }),
        fetch("/api/admin/orders", { cache: "no-store" }),
      ]);
      if (!stats.ok || !list.ok) throw new Error("تعذر تحميل بيانات التشغيل");
      setAdmin(person);
      setOverview(await stats.json());
      setOrders(await list.json());
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
    if (result.ok) { setAdmin(null); setOverview(null); setOrders([]); }
    else setError("تعذر تسجيل الخروج");
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
    </section>
    <section style={card}><h2>آخر الطلبات</h2><div style={{ overflowX: "auto" }}><table style={{ width: "100%", borderCollapse: "collapse", textAlign: "right" }}>
      <thead><tr><th>الطلب</th><th>الخدمة</th><th>الحالة</th><th>القيمة</th><th>التاريخ</th></tr></thead>
      <tbody>{orders.map(order => <tr key={order.id} style={{ borderTop: "1px solid #e6ebed" }}>
        <td style={{ padding: 12 }} dir="ltr">{order.id.slice(0, 8)}</td><td>{order.service_name}</td><td>{order.status}{order.failed_jobs > 0 ? " · مهمة فاشلة" : ""}</td>
        <td>{currency(order.price_snapshot_halalas)}</td><td>{new Date(order.created_at).toLocaleString("ar-SA")}</td>
      </tr>)}</tbody></table>{!orders.length && <p>لا توجد طلبات بعد.</p>}</div></section>
  </main>;
}
