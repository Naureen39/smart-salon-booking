import SiteLayout from "@/components/layout/SiteLayout";
import { usePageTitle } from "@/hooks/usePageTitle";

// Placeholder imagery (Lorem Picsum — free-to-use stock photography) until the
// salon's own photography is available; see docs plan §11.2.
const GALLERY_IMAGES = [
  { seed: "glowdesk-gallery-1", alt: "Close-up of a finished balayage hair color" },
  { seed: "glowdesk-gallery-2", alt: "Manicure station with soft natural light" },
  { seed: "glowdesk-gallery-3", alt: "Relaxing spa treatment room" },
];

const TEAM = [
  { name: "Elena Rossi", title: "Founder & Master Stylist", bio: "15 years behind the chair, specializing in color correction." },
  { name: "Marcus Chen", title: "Senior Stylist", bio: "Known for precision cuts and a calm, unhurried approach." },
  { name: "Sofia Ibrahim", title: "Spa Lead", bio: "Certified esthetician focused on skin health and relaxation." },
];

export default function About() {
  usePageTitle("About");

  return (
    <SiteLayout>
      <section className="mx-auto max-w-4xl px-6 py-16">
        <h1 className="font-display text-4xl text-neutral-900">Our Story</h1>
        <p className="mt-4 text-neutral-600">
          GlowDesk started with a simple idea: booking a haircut shouldn't feel like a chore. We opened our first
          chair with a promise to blend genuine craft with technology that respects your time — from a booking
          assistant that actually understands "next Saturday afternoon" to reminders that show up exactly when
          you need them, not a fixed number of hours before.
        </p>
        <p className="mt-4 text-neutral-600">
          Today our team brings decades of combined experience across hair, nails, and skincare, and every
          appointment is backed by the same care whether you booked online, by chat, or over the phone.
        </p>
      </section>

      <section className="bg-neutral-50 py-16">
        <div className="mx-auto max-w-6xl px-6">
          <h2 className="font-display text-2xl text-neutral-900">Meet the Team</h2>
          <div className="mt-6 grid gap-6 sm:grid-cols-3">
            {TEAM.map((member) => (
              <div key={member.name} className="rounded-2xl bg-white p-6 text-center shadow-sm">
                <div className="mx-auto h-20 w-20 rounded-full bg-brand/10" aria-hidden="true" />
                <p className="mt-4 font-display text-lg text-neutral-900">{member.name}</p>
                <p className="text-sm font-medium text-brand">{member.title}</p>
                <p className="mt-2 text-sm text-neutral-600">{member.bio}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 py-16">
        <h2 className="font-display text-2xl text-neutral-900">Gallery</h2>
        <div className="mt-6 grid gap-4 sm:grid-cols-3">
          {GALLERY_IMAGES.map((image) => (
            <img
              key={image.seed}
              src={`https://picsum.photos/seed/${image.seed}/600/450`}
              alt={image.alt}
              className="h-56 w-full rounded-2xl object-cover"
              loading="lazy"
            />
          ))}
        </div>
      </section>
    </SiteLayout>
  );
}
