import { useEffect, useState } from "react";

export type Page = "map" | "commute" | "about" | "methodology" | "data";

/** The text pages shown over the map. "map" and "commute" are the two map modes. */
export type InfoPageName = Exclude<Page, "map" | "commute">;

export const isInfoPage = (page: Page): page is InfoPageName =>
  page !== "map" && page !== "commute";

const PAGES: Page[] = ["commute", "about", "methodology", "data"];

function pageFromHash(): Page {
  const name = window.location.hash.replace(/^#\/?/, "");
  return (PAGES as string[]).includes(name) ? (name as Page) : "map";
}

export function useHashPage(): Page {
  const [page, setPage] = useState(pageFromHash);
  useEffect(() => {
    const onChange = () => setPage(pageFromHash());
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return page;
}
