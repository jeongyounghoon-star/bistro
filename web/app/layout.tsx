import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "BISTRO · 한국 거시금융 예측 대시보드",
  description:
    "BIS Time-series Regression Oracle 기반 한국 거시·금융 시계열 예측 대시보드",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
