import SiteLayout from "@/components/layout/SiteLayout";
import { usePageTitle } from "@/hooks/usePageTitle";

// Real, verified photography (Unsplash, free license, no attribution
// required), picked to actually match each caption and free of any other
// business's visible branding.
const GALLERY_IMAGES = [
  {
    url: "https://images.unsplash.com/photo-1600334129128-685c5582fd35?q=80&w=700&auto=format&fit=crop",
    alt: "Hot stone massage treatment with white orchids on the table",
  },
  {
    url: "https://images.unsplash.com/photo-1659391542239-9648f307c0b1?q=80&w=700&auto=format&fit=crop",
    alt: "Nail technician applying polish during a manicure",
  },
  {
    url: "https://images.unsplash.com/photo-1695527081827-fdbc4e77be9b?q=80&w=700&auto=format&fit=crop",
    alt: "Bright, plant-accented styling and wash station",
  },
  {
    url: "https://images.unsplash.com/photo-1707720531504-ce087725861a?q=80&w=700&auto=format&fit=crop",
    alt: "Stylist applying color during a client appointment",
  },
];

const TEAM = [
  {
    name: "Elena Rossi",
    title: "Founder & Master Stylist",
    bio: "15 years behind the chair, specializing in color correction.",
    photo: "https://images.unsplash.com/photo-1580489944761-15a19d654956?q=80&w=400&auto=format&fit=crop",
  },
  {
    name: "Marcus Chen",
    title: "Senior Stylist",
    bio: "Known for precision cuts and a calm, unhurried approach.",
    photo: "https://images.unsplash.com/photo-1592234789031-94bf65f630ed?q=80&w=400&auto=format&fit=crop",
  },
  {
    name: "Sofia Ibrahim",
    title: "Spa Lead",
    bio: "Certified esthetician focused on skin health and relaxation.",
    photo: "https://images.unsplash.com/photo-1494790108377-be9c29b29330?q=80&w=400&auto=format&fit=crop",
  },
];

export default function About() {
  usePageTitle("About");

  return (
    <SiteLayout>
      <section className="mx-auto max-w-4xl px-6 py-16">
        <h1 className="font-display text-4xl text-neutral-900">Our Story</h1>
        <p className="mt-4 text-neutral-600">
          GlowDesk started with a simple idea: booking a haircut shouldn't feel like a chore. We opened our first
          chair with a promise to blend genuine craft with technology that respects your time: from a booking
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
                <img
                  src={member.photo}
                  alt={`Portrait of ${member.name}`}
                  className="mx-auto h-24 w-24 rounded-full object-cover"
                  loading="lazy"
                />
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
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {GALLERY_IMAGES.map((image) => (
            <img
              key={image.url}
              src={image.url}
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
