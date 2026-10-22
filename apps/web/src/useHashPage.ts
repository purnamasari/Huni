import { useEffect, useState } from "react";

export type Page = "map" | "about" | "methodology" | "data";

const PAGES: Page[] = ["about", "methodology", "data"];

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
