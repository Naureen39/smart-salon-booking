// Curated, verified photography used when a service has no `image_url` of its
// own set yet (there's no seed script for service images, so this keeps the
// site looking like a real salon out of the box rather than showing broken
// or placeholder images). Sourced from Unsplash (free license, no
// attribution required) and picked by category keyword rather than a single
// generic fallback, so a "Hair" service and a "Nails" service don't show the
// same photo.
const CATEGORY_FALLBACKS: { keywords: string[]; url: string }[] = [
  {
    keywords: ["hair", "cut", "trim", "style", "blowout"],
    url: "https://images.unsplash.com/photo-1701885183616-cf00e2db1a3b?q=80&w=800&auto=format&fit=crop",
  },
  {
    keywords: ["color", "colour", "balayage", "highlight", "dye"],
    url: "https://images.unsplash.com/photo-1785456390070-9960e3997066?q=80&w=800&auto=format&fit=crop",
  },
  {
    keywords: ["nail", "manicure", "pedicure"],
    url: "https://images.unsplash.com/photo-1772322586754-34c9e6f5be6f?q=80&w=800&auto=format&fit=crop",
  },
  {
    keywords: ["spa", "massage", "facial", "skin", "wellness"],
    url: "https://images.unsplash.com/photo-1706795033728-9232ef548a16?q=80&w=800&auto=format&fit=crop",
  },
];

const DEFAULT_FALLBACK =
  "https://images.unsplash.com/photo-1746723378067-83a345ff3160?q=80&w=800&auto=format&fit=crop";

export function fallbackServiceImage(category: string | null): string {
  const lowered = category?.toLowerCase() ?? "";
  const match = CATEGORY_FALLBACKS.find((entry) => entry.keywords.some((keyword) => lowered.includes(keyword)));
  return match?.url ?? DEFAULT_FALLBACK;
}

export function serviceImage(service: { image_url: string | null; category: string | null }): string {
  return service.image_url ?? fallbackServiceImage(service.category);
}
