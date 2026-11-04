/** Travel time on the 0–100 score scale: 20 min or less is 90+, 70 min is 40. */
export function commuteScore(minutes: number | null | undefined): number | null {
  if (minutes === null || minutes === undefined) return null;
  return Math.max(0, Math.min(100, Math.round(110 - minutes)));
}

/** Short label for a map badge. */
export const commuteBadge = (minutes: number | null | undefined) =>
  minutes === null || minutes === undefined ? "–" : `${Math.round(minutes)}m`;

/** Today at the given "HH:MM", as the naive local time the API expects. */
export function todayAt(time: string): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${time}:00`;
}
