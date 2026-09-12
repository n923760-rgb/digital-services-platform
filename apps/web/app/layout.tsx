import type { Metadata } from "next";

export const metadata: Metadata = { title: "Digital Services Platform" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="ar" dir="rtl"><body style={{ fontFamily: "system-ui", margin: "3rem" }}>{children}</body></html>;
}
