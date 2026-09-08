import { NavLink } from "react-router-dom";

const links = [
  { to: "/", label: "Home" },
  { to: "/services", label: "Services" },
  { to: "/about", label: "About" },
  { to: "/contact", label: "Contact" },
];

function navLinkClass({ isActive }: { isActive: boolean }): string {
  return isActive
    ? "text-sm font-medium text-brand"
    : "text-sm font-medium text-neutral-600 hover:text-brand";
}

export default function Navbar() {
  return (
    <header className="sticky top-0 z-40 border-b border-neutral-100 bg-white/90 backdrop-blur">
      <nav className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <NavLink to="/" className="font-display text-xl text-brand">
          GlowDesk
        </NavLink>
        <div className="hidden items-center gap-6 sm:flex">
          {links.map((link) => (
            <NavLink key={link.to} to={link.to} className={navLinkClass} end={link.to === "/"}>
              {link.label}
            </NavLink>
          ))}
        </div>
        <NavLink
          to="/services"
          className="rounded-full bg-brand px-5 py-2 text-sm font-medium text-white shadow-sm hover:bg-brand-light"
        >
          Book Now
        </NavLink>
      </nav>
    </header>
  );
}
