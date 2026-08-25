"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Parlay } from "@/types/sports";

export default function ParlayCard() {
  const [parlay, setParlay] = useState<Parlay | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .parlay()
      .then(setParlay)
      .catch(() => setParlay(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="text-[#8b98a9] text-sm py-4">주력 조합 분석 중…</div>;
  }
  if (!parlay || parlay.legs.length < 2) {
    return (
      <div className="bg-board-card border border-board-border rounded-xl p-4 text-[#8b98a9] text-sm">
        오늘 신뢰도 80% 이상의 주력 픽이 2개 미만입니다. 경기 시작 3시간 전 자동 갱신됩니다.
      </div>
    );
  }

  return (
    <div className="bg-board-card border border-led-gold/40 rounded-xl p-4 shadow-glow-gold">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-led-gold font-black tracking-widest text-sm">
          🔥 AI 주력 {parlay.legs.length}폴더 조합
        </h3>
        <span className="text-xs text-[#8b98a9]">
          결합 신뢰도 <span className="text-led-gold font-bold tabular">{parlay.combined_confidence}%</span>
        </span>
      </div>
      <ol className="space-y-2">
        {parlay.legs.map((leg, i) => (
          <li
            key={leg.game_id}
            className="flex items-center justify-between bg-board-card2 border border-board-border rounded-lg px-3 py-2"
          >
            <div className="flex items-center gap-2">
              <span className="text-led-gold font-black">{i + 1}</span>
              <span className="text-sm">{leg.match}</span>
            </div>
            <div className="flex items-center gap-2 text-xs">
              <span className="led-chip" style={{ color: "#00FF87", borderColor: "#00FF87" }}>
                {leg.pick === "home" ? "홈" : leg.pick === "away" ? "원정" : "무"}
              </span>
              <span className="text-[#8b98a9] tabular">{leg.confidence}%</span>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
