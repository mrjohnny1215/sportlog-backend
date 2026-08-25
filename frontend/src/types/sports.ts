export type Sport = "baseball" | "football" | "basketball" | "volleyball" | "hockey";

export type LinePick = "home" | "away" | "draw" | "over" | "under" | "NRFI" | "YRFI";

export interface Prediction {
  ml_home_pct: number;
  ml_draw_pct: number;
  ml_away_pct: number;
  ml_pick: "home" | "away" | "draw";
  hc_line: number;
  hc_pick: "home" | "away";
  hc_cover_pct: number;
  tot_line: number;
  tot_pick: "over" | "under";
  tot_pct: number;
  nrfi_pct: number | null;
  yrfi_pct: number | null;
  nrfi_pick: "NRFI" | "YRFI" | null;
  value_bet: boolean;
  value_bet_detail: string | null;
  confidence: number;
  ai_summary: string | null;
  resolved: boolean;
  ml_correct: boolean | null;
  hc_correct: boolean | null;
  tot_correct: boolean | null;
  nrfi_correct: boolean | null;
}

export interface Game {
  id: string;
  sport: Sport;
  league: string;
  game_datetime: string | null;
  status: string;
  home_team_id: string;
  away_team_id: string;
  home_team_name: string;
  away_team_name: string;
  venue_id: string | null;
  home_score: number | null;
  away_score: number | null;
  home_starter: string | null;
  away_starter: string | null;
  home_starter_era: number | null;
  away_starter_era: number | null;
  is_dome: boolean;
  prediction: Prediction | null;
}

export interface ParlayLeg {
  game_id: string;
  match: string;
  pick: "home" | "away" | "draw";
  confidence: number;
}

export interface Parlay {
  legs: ParlayLeg[];
  combined_confidence: number;
}

export interface HitRate {
  period: string;
  samples: number;
  lines: {
    moneyline: number | null;
    handicap: number | null;
    totals: number | null;
    nrfi: number | null;
  };
  overall: number | null;
}

export interface Votes {
  total: number;
  home_pct: number;
  away_pct: number;
  draw_pct: number;
}

export interface PredictionDetail {
  game: Game;
  h2h: { home_wins: number; away_wins: number; draws: number; games: number };
  momentum: { home: number[]; away: number[] };
}
