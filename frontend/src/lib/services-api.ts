import { apiFetch } from "@/lib/api-client";

export interface Service {
  id: string;
  name: string;
  description: string | null;
  category: string | null;
  duration_minutes: number;
  price_cents: number;
  image_url: string | null;
  is_active: boolean;
}

export function listServices(): Promise<Service[]> {
  return apiFetch<Service[]>("/api/v1/services");
}

export function formatPrice(cents: number): string {
  return `$${(cents / 100).toFixed(0)}`;
}
