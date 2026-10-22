export function Logo() {
  return (
    <a className="logo" href="#/" aria-label="Huni home">
      <svg viewBox="0 0 32 32" width="28" height="28" aria-hidden="true">
        <path d="M16 3 4 10v12l12 7 12-7V10z" fill="#1f3d2b" />
        <path d="M16 3v26l12-7V10z" fill="#46a359" />
        <path d="M10 18.5 16 14l6 4.5V24h-4v-4h-4v4h-4z" fill="#fff" />
      </svg>
      <span>Huni</span>
    </a>
  );
}
