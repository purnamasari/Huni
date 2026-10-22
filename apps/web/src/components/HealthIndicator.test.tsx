import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { HealthIndicator } from "./HealthIndicator";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

test("shows ok when the API health check succeeds", async () => {
  const fetchMock = vi.fn().mockResolvedValue(new Response("{}", { status: 200 }));
  vi.stubGlobal("fetch", fetchMock);

  render(<HealthIndicator />);

  expect(await screen.findByText("API: ok")).toBeTruthy();
  expect(fetchMock).toHaveBeenCalledWith("/api/health", expect.anything());
});

test("shows unavailable when the API health check fails", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("{}", { status: 503 })));

  render(<HealthIndicator />);

  expect(await screen.findByText("API: unavailable")).toBeTruthy();
});
