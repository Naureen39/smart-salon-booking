import { useEffect, useState } from "react";

import SiteLayout from "@/components/layout/SiteLayout";
import { usePageTitle } from "@/hooks/usePageTitle";
import { fallbackServiceImage } from "@/lib/service-images";
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
      .catch(() => setError("Couldn't load our service menu right now, please try again shortly."));
  }, []);

  const grouped = groupByCategory(services);

  return (
    <SiteLayout>
      <section className="mx-auto max-w-4xl px-6 py-16 text-center">
        <h1 className="font-display text-4xl text-neutral-900">Our Menu</h1>
        <p className="mx-auto mt-3 max-w-2xl text-neutral-600">
          Every treatment is performed by a licensed, insured professional. Prices reflect our standard rates,
          ask your stylist about add-ons and packages.
        </p>

        {error && <p className="mt-8 rounded-lg bg-red-50 p-4 text-sm text-red-600">{error}</p>}
        {services.length === 0 && !error && <p className="mt-12 text-neutral-500">Loading our menu…</p>}
      </section>

      {Array.from(grouped.entries()).map(([category, categoryServices]) => (
        <section key={category} className="mx-auto max-w-4xl px-6 pb-16">
          <div className="overflow-hidden rounded-3xl border border-neutral-200 bg-white shadow-sm">
            <div className="relative h-36 w-full sm:h-44">
              <img
                src={fallbackServiceImage(category)}
                alt={`${category} treatments at GlowDesk`}
                className="h-full w-full object-cover"
                loading="lazy"
              />
              <div className="absolute inset-0 flex items-end bg-gradient-to-t from-black/55 to-transparent">
                <h2 className="px-8 pb-4 font-display text-3xl text-white">{category}</h2>
              </div>
            </div>

            <dl className="divide-y divide-neutral-100 px-8 py-6">
              {categoryServices.map((service) => (
                <div key={service.id} className="flex flex-col gap-1 py-4 first:pt-0 last:pb-0">
                  <div className="flex items-baseline gap-3">
                    <dt className="font-display text-lg text-neutral-900">{service.name}</dt>
                    <span
                      className="h-px flex-1 border-b border-dotted border-neutral-300"
                      aria-hidden="true"
                    />
                    <dd className="whitespace-nowrap text-lg font-semibold text-brand">
                      {formatPrice(service.price_cents)}
                    </dd>
                  </div>
                  <div className="flex items-center justify-between gap-3 text-sm text-neutral-500">
                    {service.description ? <p className="max-w-lg">{service.description}</p> : <span />}
                    <span className="whitespace-nowrap">{service.duration_minutes} min</span>
                  </div>
                </div>
              ))}
            </dl>
          </div>
        </section>
      ))}
    </SiteLayout>
  );
}
