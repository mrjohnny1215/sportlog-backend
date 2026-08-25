import type {
  Game,
  Parlay,
  HitRate,
  Votes,
  PredictionDetail,
} from "@/types/sports";

const API =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_BASE ||
  "https://word-investigate-director-establishing.trycloudflare.com";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API}/api${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`API ${path} failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  games: (params?: { date?: string; sport?: string; league?: string }) => {
    const q = new URLSearchParams();
    if (params?.date) q.set("date", params.date);
    if (params?.sport) q.set("sport", params.sport);
    if (params?.league) q.set("league", params.league);
    const qs = q.toString();
    return get<{ count: number; games: Game[] }>(`/games${qs ? `?${qs}` : ""}`);
  },
  prediction: (gameId: string) =>
    get<PredictionDetail>(`/predictions/${gameId}`),
  parlay: () => get<Parlay>(`/parlay/today`),
  hitrate: (params?: { period?: string; sport?: string; league?: string }) => {
    const q = new URLSearchParams();
    if (params?.period) q.set("period", params.period);
    if (params?.sport) q.set("sport", params.sport);
    if (params?.league) q.set("league", params.league);
    const qs = q.toString();
    return get<HitRate>(`/hitrate${qs ? `?${qs}` : ""}`);
  },
  votes: (gameId: string) => get<Votes>(`/votes/${gameId}`),
  vote: async (gameId: string, pick: string, ip?: string) => {
    const res = await fetch(`${API}/api/vote`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ game_id: gameId, pick, ip }),
    });
    return res.json();
  },
};
