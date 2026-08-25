"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Game, Votes } from "@/types/sports";

function fmtTime(iso: string | null) {
  if (!iso) return "--:--";
  const d = new Date(iso);
  return new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(d);
}

function Led({
  label,
  value,
  color,
  picked,
}: {
  label: string;
  value: string;
  color: string;
  picked: boolean;
}) {
  return (
    <div
      className={`led-chip ${picked ? "animate-pulseLed" : ""}`}
      style={picked ? { color, borderColor: color, boxShadow: `0 0 8px ${color}88` } : { color: "#8b98a9" }}
    >
      <span>{label}</span>
      <span className="tabular">{value}</span>
    </div>
  );
}

export default function ScoreboardMatchCard({ game }: { game: Game }) {
  const [votes, setVotes] = useState<Votes | null>(null);
  const [myPick, setMyPick] = useState<string | null>(null);
  const p = game.prediction;

  useEffect(() => {
    api.votes(game.id).then(setVotes).catch(() => setVotes(null));
  }, [game.id]);

  async function cast(pick: string) {
    setMyPick(pick);
    await api.vote(game.id, pick).catch(() => {});
    api.votes(game.id).then(setVotes).catch(() => {});
  }

  const aiHome = p ? p.ml_home_pct : 50;
  const aiAway = p ? p.ml_away_pct : 50;
  const userHome = votes?.home_pct ?? 0;
  const userAway = votes?.away_pct ?? 0;

  return (
    <article className="bg-board-card border border-board-border rounded-xl p-3 shadow-[0_0_0_1px_rgba(35,41,54,0.6)]">
      {/* header row */}
      <div className="flex items-center justify-between text-xs text-[#8b98a9] mb-2">
        <div className="flex items-center gap-2">
          <span className="uppercase font-bold text-[#8b98a9]">{game.league}</span>
          {game.is_dome && (
            <span className="led-chip" style={{ color: "#00e5ff", borderColor: "#00e5ff" }}>
              🏟 돔
            </span>
          )}
          <span>{fmtTime(game.game_datetime)}</span>
        </div>
        <span className="text-[10px]">{game.sport.toUpperCase()}</span>
      </div>

      {/* teams */}
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <div className="font-bold text-base">{game.away_team_name}</div>
          <div className="text-[10px] text-[#8b98a9]">원정</div>
        </div>
        <div className="text-center px-2">
          {game.status === "final" ? (
            <div className="tabular text-2xl font-black">
              <span className={game.away_score! > game.home_score! ? "text-led-win" : ""}>
                {game.away_score}
              </span>
              <span className="text-[#8b98a9] mx-1">:</span>
              <span className={game.home_score! > game.away_score! ? "text-led-win" : ""}>
                {game.home_score}
              </span>
            </div>
          ) : (
            <div className="text-[#8b98a9] text-xs">VS</div>
          )}
        </div>
        <div className="flex-1 text-right">
          <div className="font-bold text-base">{game.home_team_name}</div>
          <div className="text-[10px] text-[#8b98a9]">홈</div>
        </div>
      </div>

      {/* starters */}
      {game.sport === "baseball" && (game.away_starter || game.home_starter) && (
        <div className="mt-2 text-[11px] text-[#8b98a9] flex justify-between border-t border-board-border pt-2">
          <span>
            선발(원) {game.away_starter}
            {game.away_starter_era ? ` ERA ${game.away_starter_era}` : ""}
          </span>
          <span>
            선발(홈) {game.home_starter}
            {game.home_starter_era ? ` ERA ${game.home_starter_era}` : ""}
          </span>
        </div>
      )}

      {/* LED chips: 4 lines */}
      {p && (
        <div className="mt-3 flex flex-wrap gap-2">
          <Led label="승패" value={`${p.ml_pick === "home" ? game.home_team_name : p.ml_pick === "away" ? game.away_team_name : "무"} ${p.ml_pick === "home" ? p.ml_home_pct : p.ml_pick === "away" ? p.ml_away_pct : p.ml_draw_pct}%`} color="#00FF87" picked />
          <Led label="핸디" value={`${p.hc_pick === "home" ? "홈" : "원"} ${p.hc_line} (${p.hc_cover_pct}%)`} color="#00E5FF" picked />
          <Led label="언오버" value={`${p.tot_line} ${p.tot_pick === "over" ? "OVER" : "UNDER"} (${p.tot_pct}%)`} color="#FFD000" picked />
          {p.nrfi_pick && (
            <Led
              label="1회"
              value={`${p.nrfi_pick} (${p.nrfi_pick === "NRFI" ? p.nrfi_pct : p.yrfi_pct}%)`}
              color={p.nrfi_pick === "NRFI" ? "#FF8C00" : "#A855F7"}
              picked
            />
          )}
          {p.value_bet && (
            <Led label="🔥가치역배" value="VALUE" color="#FF3B30" picked />
          )}
        </div>
      )}

      {/* confidence */}
      {p && (
        <div className="mt-2 text-[11px] text-[#8b98a9]">
          AI 신뢰도 <span className="text-led-gold font-bold tabular">{p.confidence}%</span>
        </div>
      )}

      {/* AI vs USER gauge */}
      <div className="mt-3">
        <div className="flex justify-between text-[10px] text-[#8b98a9] mb-1">
          <span>AI 예측</span>
          <span>유저 투표</span>
        </div>
        <div className="flex flex-col gap-1">
          <div className="gauge">
            <div className="ai" style={{ width: `${aiHome}%` }} />
          </div>
          <div className="gauge">
            <div className="user" style={{ width: `${userHome}%` }} />
          </div>
        </div>
        <div className="flex justify-between text-[11px] mt-1 tabular">
          <span className="text-led-win">홈 {aiHome}%</span>
          <span className="text-[#8b98a9]">vs</span>
          <span className="text-led-gold">홈 {userHome}%</span>
        </div>
      </div>

      {/* vote buttons */}
      <div className="mt-3 grid grid-cols-3 gap-2">
        {(["home", "draw", "away"] as const).map((pk) => {
          const label = pk === "home" ? game.home_team_name : pk === "away" ? game.away_team_name : "무승부";
          const disabled = game.status === "final";
          return (
            <button
              key={pk}
              disabled={disabled}
              onClick={() => cast(pk)}
              className={`py-1.5 rounded-md border text-xs font-bold transition ${
                myPick === pk
                  ? "border-led-gold text-led-gold shadow-glow-gold"
                  : "border-board-border text-[#8b98a9] hover:text-[#e6edf3]"
              } ${disabled ? "opacity-40 cursor-not-allowed" : ""}`}
            >
              {label}
            </button>
          );
        })}
      </div>
    </article>
  );
}
