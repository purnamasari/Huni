import type { TripLeg } from "../api/types";

const MODE_NAMES: Record<TripLeg["mode"], string> = {
  walk: "Walk",
  angkot: "Angkot",
  minibus: "Elf",
  bus: "Bus",
  feeder: "Feeder",
  shuttle: "Shuttle",
  rail: "Train",
};

export const modeName = (mode: TripLeg["mode"]) => MODE_NAMES[mode] ?? mode;

const rupiah = new Intl.NumberFormat("id-ID", {
  style: "currency",
  currency: "IDR",
  maximumFractionDigits: 0,
});

export const formatFare = (idr: number) => (idr === 0 ? "Free" : rupiah.format(idr));

export function formatDuration(minutes: number): string {
  const rounded = Math.max(1, Math.round(minutes));
  if (rounded < 60) return `${rounded} min`;
  const rest = rounded % 60;
  return rest ? `${Math.floor(rounded / 60)} h ${rest} min` : `${rounded / 60} h`;
}

export const formatDistance = (metres: number) =>
  metres < 1000 ? `${Math.round(metres)} m` : `${(metres / 1000).toFixed(1)} km`;

/** "08:42" from an ISO time with an offset, as the API sends Asia/Jakarta wall-clock time. */
export const formatClock = (iso: string) => iso.slice(11, 16);
