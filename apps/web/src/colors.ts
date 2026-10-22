// One-hue sequential ramp (OKLCH hue 148, lightness 0.95 → 0.40), light = lower score.
// Lightness carries the order, so it reads under colour-vision deficiency too.
export const SCORE_RAMP = ["#ddf6e0", "#a9e2b0", "#73c881", "#46a359", "#2e7b3f", "#1f542a"];

/** Scores at which each ramp step applies; values outside are clamped. */
export const SCORE_STOPS = [40, 50, 60, 70, 80, 90];

export const NO_SCORE_COLOR = "#d6d3cc";

export function scoreColor(score: number | null): string {
  if (score === null) return NO_SCORE_COLOR;
  if (score <= SCORE_STOPS[0]) return SCORE_RAMP[0];
  for (let i = 1; i < SCORE_STOPS.length; i++) {
    if (score <= SCORE_STOPS[i]) {
      const t = (score - SCORE_STOPS[i - 1]) / (SCORE_STOPS[i] - SCORE_STOPS[i - 1]);
      return mix(SCORE_RAMP[i - 1], SCORE_RAMP[i], t);
    }
  }
  return SCORE_RAMP[SCORE_RAMP.length - 1];
}

/** Text colour for a label sitting on a ramp colour. */
export function inkOn(score: number | null): string {
  return score !== null && score > 75 ? "#ffffff" : "#14231a";
}

function mix(a: string, b: string, t: number): string {
  const pa = [1, 3, 5].map((i) => parseInt(a.slice(i, i + 2), 16));
  const pb = [1, 3, 5].map((i) => parseInt(b.slice(i, i + 2), 16));
  return `#${pa
    .map((v, i) => Math.round(v + (pb[i] - v) * t).toString(16).padStart(2, "0"))
    .join("")}`;
}
