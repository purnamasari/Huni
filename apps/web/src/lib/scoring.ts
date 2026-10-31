import type { CriterionKey } from "../api/types";
import { CRITERIA } from "../criteria";

/** Overall score shown on the map: the mean of the criteria the user picked. */
export function overallScore(
  scores: Record<CriterionKey, number>,
  selected: ReadonlySet<CriterionKey>,
): number | null {
  if (selected.size === 0) return null;
  let sum = 0;
  for (const key of selected) sum += scores[key];
  return Math.round(sum / selected.size);
}

const joinLabels = (labels: string[]) =>
  labels.length <= 1 ? labels.join("") : `${labels.slice(0, -1).join(", ")} and ${labels.at(-1)}`;

/** A one-line, data-driven summary: what an area is strong and weak on. */
export function summarise(
  scores: Record<CriterionKey, number>,
  selected: ReadonlySet<CriterionKey>,
): string {
  const ranked = CRITERIA.filter((c) => selected.has(c.key)).sort(
    (a, b) => scores[b.key] - scores[a.key],
  );
  if (ranked.length === 0) return "Pick at least one criterion to see a score.";

  const strong = ranked.filter((c) => scores[c.key] >= 75).slice(0, 2);
  const weak = ranked.filter((c) => scores[c.key] < 60).slice(-2).reverse();
  const lower = (labels: typeof ranked) => joinLabels(labels.map((c) => c.label.toLowerCase()));

  if (strong.length && weak.length) return `Strong on ${lower(strong)}; weaker on ${lower(weak)}.`;
  if (strong.length) return `Strong on ${lower(strong)}.`;
  if (weak.length) return `Weakest on ${lower(weak)}.`;
  return "Middling across the criteria you picked.";
}
