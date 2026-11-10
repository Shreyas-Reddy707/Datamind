/**
 * Safe numeric formatting helpers preventing TypeError on null, undefined, or non-numeric JSON fields.
 */

export function toFiniteNumber(value: unknown, fallback = 0): number {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return fallback;
}

export function safeFixed(value: unknown, digits = 2, fallbackVal = 0): string {
  return toFiniteNumber(value, fallbackVal).toFixed(digits);
}

export function safeLocale(value: unknown, fallbackText = "—"): string {
  if (value === null || value === undefined || value === "") {
    return fallbackText;
  }
  const num = Number(value);
  return Number.isFinite(num) ? num.toLocaleString() : fallbackText;
}

