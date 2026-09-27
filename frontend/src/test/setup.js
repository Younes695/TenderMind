import "@testing-library/jest-dom/vitest";

// jsdom does not implement scrollTo — mock to avoid Not implemented errors in NewTender
if (typeof window !== "undefined") {
  window.scrollTo = () => {};
}
