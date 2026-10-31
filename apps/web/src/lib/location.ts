import type { Point } from "./geometry";

export const canLocate = () => typeof navigator !== "undefined" && "geolocation" in navigator;

/** The device's position as [lon, lat]. Rejects with a message fit to show the user. */
export function currentPoint(): Promise<Point> {
  return new Promise((resolve, reject) => {
    if (!canLocate()) {
      reject(new Error("This browser can't share your location."));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => resolve([coords.longitude, coords.latitude]),
      (error) =>
        reject(
          new Error(
            error.code === error.PERMISSION_DENIED
              ? "Location is blocked. Allow it for this site in your browser."
              : error.code === error.TIMEOUT
                ? "Finding your location took too long. Try again."
                : "Couldn't find your location.",
          ),
        ),
      { enableHighAccuracy: true, timeout: 10_000, maximumAge: 60_000 },
    );
  });
}
