import { ArrowUpLeft, Search, X } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import type { PlaceResult } from "../api/types";
import { canLocate } from "../lib/location";
import { usePlaceSearch } from "../usePlaceSearch";
import { CurrentLocationOption } from "./CurrentLocationOption";
import { PlaceIcon } from "./PlaceIcon";
import { SearchCredit } from "./SearchCredit";

const KIND_LABELS: Record<PlaceResult["kind"], string> = {
  kecamatan: "Kecamatan",
  kelurahan: "Kelurahan",
  area: "Area",
  street: "Street",
  landmark: "Landmark",
  address: "Address",
  point: "Exact point",
  stop: "Transit stop",
};

interface Props {
  onSelect: (place: PlaceResult) => void;
}

export function SearchBox({ onSelect }: Props) {
  const [query, setQuery] = useState("");
  const { results, searchingAddresses } = usePlaceSearch(query);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const listId = useId();
  const locate = useRef<(() => void) | null>(null);
  const empty = query.trim() === "";

  useEffect(() => setActive(0), [results]);

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
    } else if (event.key === "Enter" && open && empty) {
      event.preventDefault();
      locate.current?.();
    } else if (event.key === "Enter" && open && results[active]) {
      event.preventDefault();
      choose(results[active]);
    } else if (event.key === "Escape") {
      setOpen(false);
    }
  };

  // Empty and focused: offer the current location.
  const showList = open && (!empty || canLocate());

  return (
    <div className="search">
      <Search className="search-icon" size={18} aria-hidden="true" />
      <input
        type="search"
        role="combobox"
        aria-label="Search neighbourhoods, addresses, landmarks or coordinates"
        aria-expanded={showList}
        aria-controls={listId}
        aria-activedescendant={
          !showList ? undefined : empty ? `${listId}-here` : results[active] && `${listId}-${active}`
        }
        placeholder="Search places, addresses, or paste coordinates…"
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
          {empty && (
            <CurrentLocationOption
              id={`${listId}-here`}
              highlighted
              onHighlight={() => {}}
              onLocated={choose}
              locateRef={locate}
            />
          )}
          {!empty && results.length === 0 && !searchingAddresses && (
            <li className="search-empty">No places found</li>
          )}
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
              <PlaceIcon kind={place.kind} />
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
          {searchingAddresses && <li className="search-empty">Searching addresses…</li>}
          <SearchCredit results={results} />
        </ul>
      )}
    </div>
  );
}
