import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "BISTRO · 국내금융시장 예측 대시보드",
  description:
    "BIS Time-series Regression Oracle 기반 한국 거시/금융 시계열 예측",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
