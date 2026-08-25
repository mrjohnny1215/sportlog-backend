"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { HitRate } from "@/types/sports";

const PERIODS = [
  { key: "all", label: "전체" },
  { key: "30d", label: "최근 30일" },
  { key: "7d", label: "최근 7일" },
];

const LINES: { key: keyof HitRate["lines"]; label: string; color: string }[] = [
  { key: "moneyline", label: "승패", color: "#00FF87" },
  { key: "handicap", label: "핸디캡", color: "#00E5FF" },
  { key: "totals", label: "언더오버", color: "#FFD000" },
  { key: "nrfi", label: "1회 NRFI·YRFI", color: "#FF8C00" },
];

export default function HitRateDashboard() {
  const [period, setPeriod] = useState("30d");
  const [data, setData] = useState<HitRate | null>(null);

  useEffect(() => {
    api
      .hitrate({ period })
      .then(setData)
      .catch(() => setData(null));
  }, [period]);

  return (
    <section className="bg-board-card border border-board-border rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-black tracking-widest text-[#8b98a9]">📊 공개 적중률 대시보드</h3>
        <div className="flex gap-1">
          {PERIODS.map((p) => (
            <button
              key={p.key}
              onClick={() => setPeriod(p.key)}
              className={`px-2 py-1 text-[11px] rounded border ${
                period === p.key
                  ? "border-led-gold text-led-gold"
                  : "border-board-border text-[#8b98a9]"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {!data || data.samples === 0 ? (
        <div className="text-[#8b98a9] text-sm py-4">
          아직 정산된 예측이 없습니다. 매일 08시(KST) 자동 정산 후 적중률이 표시됩니다.
        </div>
      ) : (
        <div className="space-y-3">
          <div className="flex justify-between text-xs text-[#8b98a9]">
            <span>표본 {data.samples}경기</span>
            <span>
              종합 적중률{" "}
              <span className="text-led-win font-bold tabular">{data.overall ?? "—"}%</span>
            </span>
          </div>
          {LINES.map((l) => {
            const v = data.lines[l.key];
            return (
              <div key={l.key}>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-[#e6edf3]">{l.label}</span>
                  <span className="tabular font-bold" style={{ color: l.color }}>
                    {v == null ? "—" : `${v}%`}
                  </span>
                </div>
                <div className="gauge">
                  <div
                    style={{ width: `${v ?? 0}%`, background: l.color, boxShadow: `0 0 8px ${l.color}88` }}
                    className="h-full"
                  />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
