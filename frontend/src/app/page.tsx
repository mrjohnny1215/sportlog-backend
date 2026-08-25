"use client";

import { useEffect, useState } from "react";
import ScoreboardHeader from "@/components/ScoreboardHeader";
import ScoreboardMatchCard from "@/components/ScoreboardMatchCard";
import ParlayCard from "@/components/ParlayCard";
import HitRateDashboard from "@/components/HitRateDashboard";
import { api } from "@/lib/api";
import type { Game, Sport } from "@/types/sports";

const SPORTS: { key: Sport | "all"; emoji: string; label: string }[] = [
  { key: "all", emoji: "📺", label: "전체" },
  { key: "baseball", emoji: "⚾", label: "야구" },
  { key: "football", emoji: "⚽", label: "축구" },
  { key: "basketball", emoji: "🏀", label: "농구" },
  { key: "volleyball", emoji: "🏐", label: "배구" },
  { key: "hockey", emoji: "🏒", label: "하키" },
];

export default function Home() {
  const [tab, setTab] = useState<Sport | "all">("all");
  const [games, setGames] = useState<Game[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api
      .games({ sport: tab === "all" ? undefined : tab })
      .then((d) => setGames(d.games))
      .catch(() => setGames([]))
      .finally(() => setLoading(false));
  }, [tab]);

  return (
    <main className="max-w-5xl mx-auto px-3 pb-16">
      <ScoreboardHeader activeSport={tab} onSelect={(s) => setTab(s as Sport | "all")} sports={SPORTS} />

      <section className="mt-4">
        <h2 className="text-sm font-bold text-[#8b98a9] mb-2 tracking-widest">
          🔥 오늘의 2~3폴더 주력
        </h2>
        <ParlayCard />
      </section>

      <section className="mt-6">
        <h2 className="text-sm font-bold text-[#8b98a9] mb-2 tracking-widest">
          📋 전광판 매치 카드
        </h2>
        {loading ? (
          <div className="text-center py-10 text-[#8b98a9]">불러오는 중…</div>
        ) : games.length === 0 ? (
          <div className="text-center py-10 text-[#8b98a9]">오늘 예정된 경기가 없습니다.</div>
        ) : (
          <div className="grid grid-cols-1 gap-4">
            {games.map((g) => (
              <ScoreboardMatchCard key={g.id} game={g} />
            ))}
          </div>
        )}
      </section>

      <section className="mt-8">
        <HitRateDashboard />
      </section>
    </main>
  );
}
