import { ArrowUpLeft, MapPin, Search, X } from "lucide-react";
import { useEffect, useId, useState } from "react";
import { searchPlaces } from "../api/client";
import type { PlaceResult } from "../api/types";

const KIND_LABELS: Record<PlaceResult["kind"], string> = {
  kecamatan: "Kecamatan",
  kelurahan: "Kelurahan",
  area: "Area",
  street: "Street",
  landmark: "Landmark",
};

interface Props {
  onSelect: (place: PlaceResult) => void;
}

export function SearchBox({ onSelect }: Props) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<PlaceResult[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const listId = useId();

  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(() => {
      searchPlaces(query, controller.signal)
        .then((found) => {
          setResults(found);
          setActive(0);
        })
        .catch(() => {
          if (!controller.signal.aborted) setResults([]);
        });
    }, 120);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query]);

  const choose = (place: PlaceResult) => {
    setQuery(place.name);
    setOpen(false);
    onSelect(place);
  };

  const onKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setOpen(true);
      setActive((i) => Math.min(i + 1, results.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (event.key === "Enter" && open && results[active]) {
      event.preventDefault();
      choose(results[active]);
    } else if (event.key === "Escape") {
      setOpen(false);
    }
  };

  const showList = open && query.trim() !== "";

  return (
    <div className="search">
      <Search className="search-icon" size={18} aria-hidden="true" />
      <input
        type="search"
        role="combobox"
        aria-label="Search neighbourhoods, streets or landmarks"
        aria-expanded={showList}
        aria-controls={listId}
        aria-activedescendant={showList && results[active] ? `${listId}-${active}` : undefined}
        placeholder="Search neighbourhoods, streets, or landmarks…"
        value={query}
        onChange={(event) => {
          setQuery(event.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={onKeyDown}
      />
      {query && (
        <button
          type="button"
          className="icon-button search-clear"
          aria-label="Clear search"
          onClick={() => setQuery("")}
        >
          <X size={18} />
        </button>
      )}
      {showList && (
        <ul className="search-results" id={listId} role="listbox">
          {results.length === 0 && <li className="search-empty">No places found</li>}
          {results.map((place, index) => (
            <li
              key={place.id}
              id={`${listId}-${index}`}
              role="option"
              aria-selected={index === active}
              className="search-result"
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => choose(place)}
              onMouseEnter={() => setActive(index)}
            >
              <MapPin size={18} className="search-result-pin" aria-hidden="true" />
              <span className="search-result-text">
                <span className="search-result-name">{place.name}</span>
                <span className="search-result-context">
                  {KIND_LABELS[place.kind]} · {place.context}
                </span>
              </span>
              {!place.insideKota && <span className="tag tag-muted">Outside Kota</span>}
              {index === active && (
                <ArrowUpLeft size={16} className="search-result-go" aria-hidden="true" />
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
