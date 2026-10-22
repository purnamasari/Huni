import {
  BriefcaseBusiness,
  Bus,
  type LucideIcon,
  School,
  ShoppingCart,
  Trees,
  Waves,
} from "lucide-react";
import type { CriterionKey } from "./api/types";

export interface Criterion {
  key: CriterionKey;
  label: string;
  icon: LucideIcon;
  measures: string;
  sources: string;
}

export const CRITERIA: Criterion[] = [
  {
    key: "parks",
    label: "Parks & green space",
    icon: Trees,
    measures: "Distance to the nearest public park, and park area per resident.",
    sources: "OpenStreetMap",
  },
  {
    key: "schools",
    label: "Schools",
    icon: School,
    measures: "Schools nearby and distance to the nearest one.",
    sources: "Kemendikbud Data Referensi, OpenStreetMap",
  },
  {
    key: "angkot",
    label: "Angkot access",
    icon: Bus,
    measures: "Distance to angkot routes and stops.",
    sources: "OpenStreetMap, Dishub Kota Bandung",
  },
  {
    key: "dailyNeeds",
    label: "Daily needs",
    icon: ShoppingCart,
    measures: "Markets, minimarkets and pharmacies within walking distance.",
    sources: "OpenStreetMap",
  },
  {
    key: "commute",
    label: "Work commute",
    icon: BriefcaseBusiness,
    measures: "Travel distance to the main employment centres.",
    sources: "OpenStreetMap road network",
  },
];

export const FLOOD = {
  label: "Flood risk",
  icon: Waves,
  measures: "Historical flood events and hazard maps. Shown as a warning, not scored.",
  sources: "BNPB InaRISK, BPBD Kota Bandung",
};

export const FLOOD_LABELS = { low: "Low", moderate: "Moderate", high: "High" } as const;
