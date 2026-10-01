import Link from "next/link";

export default function Home() {
  return <main><h1>منصة الخدمات الرقمية</h1>
    <p>خدمات العملاء عبر بوت تيليجرام. هذه الواجهة مخصصة لإدارة التشغيل.</p>
    <Link href="/admin">الدخول إلى لوحة التشغيل</Link>
  </main>;
}
