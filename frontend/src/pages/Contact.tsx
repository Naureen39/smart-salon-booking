import { type FormEvent, useState } from "react";

import SiteLayout from "@/components/layout/SiteLayout";
import { usePageTitle } from "@/hooks/usePageTitle";

// OpenStreetMap embed — no API key required, unlike Google Maps. Coordinates
// are a placeholder pin pending the salon's real address being finalized.
const MAP_EMBED_SRC =
  "https://www.openstreetmap.org/export/embed.html?bbox=-122.42%2C37.77%2C-122.40%2C37.79&layer=mapnik";

export default function Contact() {
  usePageTitle("Contact");
  const [form, setForm] = useState({ name: "", email: "", message: "" });
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    // No backend endpoint exists yet for contact-form submissions (out of
    // scope for this phase) — mailto is an honest, working stand-in rather
    // than a form that silently does nothing.
    const subject = encodeURIComponent(`Message from ${form.name || "website visitor"}`);
    const body = encodeURIComponent(`${form.message}\n\nReply to: ${form.email}`);
    window.location.href = `mailto:hello@glowdesk.example?subject=${subject}&body=${body}`;
    setSubmitted(true);
  };

  return (
    <SiteLayout>
      <section className="mx-auto max-w-6xl px-6 py-16">
        <h1 className="font-display text-4xl text-neutral-900">Get in Touch</h1>
        <p className="mt-3 max-w-2xl text-neutral-600">
          Questions about a service, a booking, or just want to say hi? Reach out — we usually reply within a
          business day.
        </p>

        <div className="mt-10 grid gap-10 lg:grid-cols-2">
          <div>
            <dl className="space-y-4 text-sm">
              <div>
                <dt className="font-semibold text-neutral-800">Address</dt>
                <dd className="text-neutral-600">123 Bloom Street, Suite 4, Springfield, ST 00000</dd>
              </div>
              <div>
                <dt className="font-semibold text-neutral-800">Phone</dt>
                <dd className="text-neutral-600">(555) 010-2024</dd>
              </div>
              <div>
                <dt className="font-semibold text-neutral-800">Hours</dt>
                <dd className="text-neutral-600">Tuesday–Saturday, 9:00 AM–6:00 PM</dd>
              </div>
              <div>
                <dt className="font-semibold text-neutral-800">Parking</dt>
                <dd className="text-neutral-600">Free customer parking directly behind the salon.</dd>
              </div>
            </dl>
            <iframe
              title="GlowDesk location map"
              src={MAP_EMBED_SRC}
              className="mt-6 h-64 w-full rounded-2xl border border-neutral-200"
              loading="lazy"
            />
          </div>

          <form onSubmit={handleSubmit} className="space-y-4 rounded-2xl border border-neutral-200 p-6 shadow-sm">
            <div>
              <label htmlFor="contact-name" className="text-sm font-medium text-neutral-700">
                Name
              </label>
              <input
                id="contact-name"
                type="text"
                required
                value={form.name}
                onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
                className="mt-1 w-full rounded-lg border border-neutral-300 px-3 py-2 text-sm focus:border-brand focus:outline-none"
              />
            </div>
            <div>
              <label htmlFor="contact-email" className="text-sm font-medium text-neutral-700">
                Email
              </label>
              <input
                id="contact-email"
                type="email"
                required
                value={form.email}
                onChange={(event) => setForm((prev) => ({ ...prev, email: event.target.value }))}
                className="mt-1 w-full rounded-lg border border-neutral-300 px-3 py-2 text-sm focus:border-brand focus:outline-none"
              />
            </div>
            <div>
              <label htmlFor="contact-message" className="text-sm font-medium text-neutral-700">
                Message
              </label>
              <textarea
                id="contact-message"
                required
                rows={4}
                value={form.message}
                onChange={(event) => setForm((prev) => ({ ...prev, message: event.target.value }))}
                className="mt-1 w-full rounded-lg border border-neutral-300 px-3 py-2 text-sm focus:border-brand focus:outline-none"
              />
            </div>
            <button
              type="submit"
              className="w-full rounded-full bg-brand px-6 py-3 text-sm font-semibold text-white hover:bg-brand-light"
            >
              Send Message
            </button>
            {submitted && (
              <p className="text-sm text-neutral-500">Opening your email client to send this message…</p>
            )}
          </form>
        </div>
      </section>
    </SiteLayout>
  );
}
