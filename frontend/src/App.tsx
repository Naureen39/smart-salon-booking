import { Route, Routes } from "react-router-dom";

import ChatWidget from "@/components/assistant/ChatWidget";
import About from "@/pages/About";
import AdminDashboard from "@/pages/AdminDashboard";
import Contact from "@/pages/Contact";
import Home from "@/pages/Home";
import Services from "@/pages/Services";

export default function App() {
  return (
    <>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/services" element={<Services />} />
        <Route path="/about" element={<About />} />
        <Route path="/contact" element={<Contact />} />
        {/* accessToken is null until frontend login/auth state is built (not part of Phase 10's scope) */}
        <Route path="/admin" element={<AdminDashboard accessToken={null} />} />
      </Routes>
      <ChatWidget accessToken={null} />
    </>
  );
}
