import { useEffect, useState } from "react";

type State = "checking" | "ok" | "error";

const LABELS: Record<State, string> = {
  checking: "API: checking…",
  ok: "API: ok",
  error: "API: unavailable",
};

export function HealthIndicator() {
  const [state, setState] = useState<State>("checking");

  useEffect(() => {
    const controller = new AbortController();

    fetch("/api/health", { signal: controller.signal })
      .then((response) => setState(response.ok ? "ok" : "error"))
      .catch(() => {
        if (!controller.signal.aborted) setState("error");
      });

    return () => controller.abort();
  }, []);

  return (
    <div className="health" data-state={state} role="status">
      {LABELS[state]}
    </div>
  );
}
