import { useEffect, useState } from "react";

import SiteLayout from "@/components/layout/SiteLayout";
import { usePageTitle } from "@/hooks/usePageTitle";
import { formatPrice, listServices, type Service } from "@/lib/services-api";

function groupByCategory(services: Service[]): Map<string, Service[]> {
  const groups = new Map<string, Service[]>();
  for (const service of services) {
    const category = service.category ?? "Other";
    const existing = groups.get(category) ?? [];
    existing.push(service);
    groups.set(category, existing);
  }
  return groups;
}

export default function Services() {
  usePageTitle("Services");
  const [services, setServices] = useState<Service[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listServices()
      .then(setServices)
      .catch(() => setError("Couldn't load our service menu right now — please try again shortly."));
  }, []);

  const grouped = groupByCategory(services);

  return (
    <SiteLayout>
      <section className="mx-auto max-w-6xl px-6 py-16">
        <h1 className="font-display text-4xl text-neutral-900">Our Services</h1>
        <p className="mt-3 max-w-2xl text-neutral-600">
          Every treatment is performed by a licensed, insured professional. Prices reflect our standard rates —
          ask your stylist about add-ons and packages.
        </p>

        {error && <p className="mt-8 rounded-lg bg-red-50 p-4 text-sm text-red-600">{error}</p>}

        {Array.from(grouped.entries()).map(([category, categoryServices]) => (
          <div key={category} className="mt-12">
            <h2 className="font-display text-2xl text-brand">{category}</h2>
            <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {categoryServices.map((service) => (
                <article key={service.id} className="rounded-2xl border border-neutral-200 p-5 shadow-sm">
                  <h3 className="font-display text-lg text-neutral-900">{service.name}</h3>
                  {service.description && <p className="mt-2 text-sm text-neutral-600">{service.description}</p>}
                  <div className="mt-4 flex items-center justify-between">
                    <span className="text-sm text-neutral-500">{service.duration_minutes} min</span>
                    <span className="text-lg font-semibold text-brand">{formatPrice(service.price_cents)}</span>
                  </div>
                </article>
              ))}
            </div>
          </div>
        ))}

        {services.length === 0 && !error && <p className="mt-12 text-neutral-500">Loading our menu…</p>}
      </section>
    </SiteLayout>
  );
}
