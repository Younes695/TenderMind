import "@testing-library/jest-dom/vitest";

// jsdom does not implement scrollTo — mock to avoid Not implemented errors in NewTender
if (typeof window !== "undefined") {
  window.scrollTo = () => {};
}

// Deletions ask for confirmation (Stage 5H); tests accept by default and
// override with vi.spyOn(window, "confirm") when they test the "cancel" path.
if (typeof window !== "undefined") {
  window.confirm = () => true;
}
