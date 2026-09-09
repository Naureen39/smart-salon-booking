import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import SiteLayout from "@/components/layout/SiteLayout";
import { usePageTitle } from "@/hooks/usePageTitle";
import { serviceImage } from "@/lib/service-images";
import { formatPrice, listServices, type Service } from "@/lib/services-api";

// Real, verified salon photography (Unsplash, free license, no attribution
// required) picked to actually match the subject: no random unrelated stock
// photo, no competing business's branding visible in frame.
const HERO_IMAGE = "https://images.unsplash.com/photo-1746723378067-83a345ff3160?q=80&w=1400&auto=format&fit=crop";
const SPACE_IMAGE = "https://images.unsplash.com/photo-1781450090585-1a511b7066d9?q=80&w=1600&auto=format&fit=crop";

const VALUE_PROPS = [
  {
    title: "Book in seconds",
    body: "Chat, talk, or click: our AI assistant fills in the details and finds you a time that works.",
  },
  {
    title: "Fewer no-shows",
    body: "Smart reminders, timed by how likely you are to forget, keep your seat (and ours) reserved.",
  },
  {
    title: "Expert care",
    body: "Every stylist on our team is trained, insured, and genuinely excited to see you.",
  },
];

const TESTIMONIALS = [
  { name: "Amara T.", quote: "Booked my haircut through the chat widget in under a minute. So easy." },
  { name: "Priya K.", quote: "The reminder texts are a lifesaver. I never double-book myself anymore." },
  { name: "Jordan L.", quote: "Best color I've had in years. The team really listens." },
];

const fadeUp = {
  hidden: { opacity: 0, y: 24 },
  visible: { opacity: 1, y: 0 },
};

export default function Home() {
  usePageTitle("Home");
  const [featuredServices, setFeaturedServices] = useState<Service[]>([]);

  useEffect(() => {
    listServices()
      .then((services) => setFeaturedServices(services.slice(0, 3)))
      .catch(() => setFeaturedServices([]));
  }, []);

  return (
    <SiteLayout>
      <section className="mx-auto grid max-w-6xl gap-10 px-6 py-16 sm:py-24 lg:grid-cols-2 lg:items-center">
        <motion.div initial="hidden" animate="visible" variants={fadeUp} transition={{ duration: 0.6 }}>
          <h1 className="font-display text-4xl leading-tight text-neutral-900 sm:text-5xl">
            Look and feel your <span className="text-brand">best</span>.
          </h1>
          <p className="mt-4 max-w-md text-lg text-neutral-600">
            GlowDesk brings expert hair, nail, and spa care to your schedule: book by web, chat, or voice, and
            we'll handle the rest.
          </p>
          <div className="mt-8 flex flex-wrap gap-4">
            <Link
              to="/services"
              className="rounded-full bg-brand px-6 py-3 text-sm font-semibold text-white shadow-sm hover:bg-brand-light"
            >
              Book Now
            </Link>
            <Link
              to="/about"
              className="rounded-full border border-neutral-300 px-6 py-3 text-sm font-semibold text-neutral-700 hover:border-brand hover:text-brand"
            >
              Meet the Team
            </Link>
          </div>
        </motion.div>
        <motion.img
          src={HERO_IMAGE}
          alt="Bright, modern salon with a stylist attending a client, surrounded by shelves of styling products"
          className="h-72 w-full rounded-3xl object-cover shadow-lg sm:h-96"
          initial={{ opacity: 0, scale: 0.97 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.7 }}
        />
      </section>

      <section className="bg-neutral-50 py-16">
        <div className="mx-auto max-w-6xl px-6">
          <div className="grid gap-8 sm:grid-cols-3">
            {VALUE_PROPS.map((prop, index) => (
              <motion.div
                key={prop.title}
                initial="hidden"
                whileInView="visible"
                viewport={{ once: true, amount: 0.4 }}
                variants={fadeUp}
                transition={{ duration: 0.5, delay: index * 0.1 }}
                className="rounded-2xl bg-white p-6 shadow-sm"
              >
                <h3 className="font-display text-lg text-brand">{prop.title}</h3>
                <p className="mt-2 text-sm text-neutral-600">{prop.body}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {featuredServices.length > 0 && (
        <section className="mx-auto max-w-6xl px-6 py-16">
          <h2 className="font-display text-2xl text-neutral-900">Featured services</h2>
          <div className="mt-6 grid gap-6 sm:grid-cols-3">
            {featuredServices.map((service) => (
              <Link
                key={service.id}
                to="/services"
                className="group overflow-hidden rounded-2xl border border-neutral-200 shadow-sm transition-shadow hover:shadow-md"
              >
                <div className="h-40 w-full overflow-hidden">
                  <img
                    src={serviceImage(service)}
                    alt={service.name}
                    className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
                    loading="lazy"
                  />
                </div>
                <div className="p-5">
                  <p className="font-display text-lg text-neutral-900">{service.name}</p>
                  <p className="mt-1 text-sm text-neutral-500">{service.duration_minutes} min</p>
                  <p className="mt-3 text-xl font-semibold text-brand">{formatPrice(service.price_cents)}</p>
                </div>
              </Link>
            ))}
          </div>
          <Link to="/services" className="mt-6 inline-block text-sm font-medium text-brand hover:underline">
            View full menu →
          </Link>
        </section>
      )}

      <section className="relative">
        <img
          src={SPACE_IMAGE}
          alt="Elegant, softly lit salon interior with arched mirror alcoves and styling chairs"
          className="h-80 w-full object-cover sm:h-[28rem]"
          loading="lazy"
        />
        <div className="absolute inset-0 flex items-center bg-black/35">
          <div className="mx-auto max-w-6xl px-6">
            <p className="max-w-md font-display text-2xl text-white sm:text-3xl">
              A space designed for you to relax, unwind, and leave feeling like yourself again.
            </p>
          </div>
        </div>
      </section>

      <section className="bg-neutral-50 py-16">
        <div className="mx-auto max-w-6xl px-6">
          <h2 className="font-display text-2xl text-neutral-900">What clients say</h2>
          <div className="mt-6 grid gap-6 sm:grid-cols-3">
            {TESTIMONIALS.map((testimonial) => (
              <blockquote key={testimonial.name} className="rounded-2xl bg-white p-6 shadow-sm">
                <p className="text-sm italic text-neutral-600">"{testimonial.quote}"</p>
                <footer className="mt-3 text-sm font-medium text-neutral-800">- {testimonial.name}</footer>
              </blockquote>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 py-16 text-center">
        <h2 className="font-display text-3xl text-neutral-900">Ready for your next appointment?</h2>
        <Link
          to="/services"
          className="mt-6 inline-block rounded-full bg-brand px-8 py-3 text-sm font-semibold text-white shadow-sm hover:bg-brand-light"
        >
          Book Now
        </Link>
      </section>
    </SiteLayout>
  );
}
