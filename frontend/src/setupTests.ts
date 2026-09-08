import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

// jsdom doesn't implement IntersectionObserver, which framer-motion's
// `whileInView` viewport feature (used on the marketing pages) needs at
// mount time. A minimal no-op stub is enough for components to render in
// tests — nothing here asserts on actual scroll-triggered behavior.
class IntersectionObserverStub {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
  takeRecords(): IntersectionObserverEntry[] {
    return [];
  }
}

vi.stubGlobal("IntersectionObserver", IntersectionObserverStub);
