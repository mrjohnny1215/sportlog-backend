"use client";

import { useEffect, useState } from "react";

interface Props {
  activeSport: string;
  onSelect: (s: string) => void;
  sports: { key: string; emoji: string; label: string }[];
}

function useKstClock() {
  const [now, setNow] = useState<string>("");
  useEffect(() => {
    const fmt = () =>
      new Intl.DateTimeFormat("ko-KR", {
        timeZone: "Asia/Seoul",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      }).format(new Date());
    setNow(fmt());
    const t = setInterval(() => setNow(fmt()), 1000);
    return () => clearInterval(t);
  }, []);
  return now;
}

export default function ScoreboardHeader({ activeSport, onSelect, sports }: Props) {
  const clock = useKstClock();
  return (
    <header className="sticky top-0 z-20 bg-board-bg/95 backdrop-blur border-b border-board-border">
      <div className="max-w-5xl mx-auto px-3 py-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-led-gold text-lg font-black tracking-widest">SPORTS·AI</span>
          <span className="text-[10px] text-[#8b98a9] hidden sm:inline">전광판 예측 엔진</span>
        </div>
        <div className="tabular text-led-win text-xl font-black drop-shadow-[0_0_6px_rgba(0,255,135,0.6)]">
          {clock}
          <span className="text-[10px] text-[#8b98a9] ml-1">KST</span>
        </div>
      </div>
      <nav className="max-w-5xl mx-auto px-3 pb-2 flex gap-2 overflow-x-auto">
        {sports.map((s) => {
          const active = activeSport === s.key;
          return (
            <button
              key={s.key}
              onClick={() => onSelect(s.key)}
              className={`shrink-0 px-3 py-1.5 rounded-md border text-sm font-bold transition ${
                active
                  ? "border-led-gold text-led-gold shadow-glow-gold"
                  : "border-board-border text-[#8b98a9] hover:text-[#e6edf3]"
              }`}
            >
              <span className="mr-1">{s.emoji}</span>
              {s.label}
            </button>
          );
        })}
      </nav>
    </header>
  );
}
