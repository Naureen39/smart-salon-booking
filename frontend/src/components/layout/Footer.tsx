export default function Footer() {
  return (
    <footer className="border-t border-neutral-100 bg-neutral-50">
      <div className="mx-auto grid max-w-6xl gap-8 px-6 py-10 sm:grid-cols-3">
        <div>
          <p className="font-display text-lg text-brand">GlowDesk</p>
          <p className="mt-2 text-sm text-neutral-500">
            Salon &amp; spa booking made effortless: by web, chat, or voice.
          </p>
        </div>
        <div>
          <p className="text-sm font-semibold text-neutral-800">Hours</p>
          <p className="mt-2 text-sm text-neutral-500">Tue–Sat: 9:00 AM – 6:00 PM</p>
          <p className="text-sm text-neutral-500">Sun–Mon: Closed</p>
        </div>
        <div>
          <p className="text-sm font-semibold text-neutral-800">Visit</p>
          <p className="mt-2 text-sm text-neutral-500">123 Bloom Street, Suite 4</p>
          <p className="text-sm text-neutral-500">Springfield, ST 00000</p>
        </div>
      </div>
      <div className="border-t border-neutral-100 px-6 py-4 text-center text-xs text-neutral-400">
        © {new Date().getFullYear()} GlowDesk. All rights reserved.
      </div>
    </footer>
  );
}
