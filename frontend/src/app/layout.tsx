import "./globals.css";
import type { ReactNode } from "react";

export const metadata = {
  title: "전광판 AI 스포츠 예측",
  description: "5대 스포츠 AI 다각도 예측 & 적중률 트래킹 전광판",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ko">
      <body className="bg-board-bg text-[#e6edf3] min-h-screen">{children}</body>
    </html>
  );
}
