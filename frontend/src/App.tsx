import { useEffect } from "react";
import { Route, Routes } from "react-router-dom";

import ChatWidget from "@/components/assistant/ChatWidget";
import About from "@/pages/About";
import AdminDashboard from "@/pages/AdminDashboard";
import Contact from "@/pages/Contact";
import Home from "@/pages/Home";
import Login from "@/pages/Login";
import Services from "@/pages/Services";
import Signup from "@/pages/Signup";
import { useAuthStore } from "@/store/auth";

export default function App() {
  const accessToken = useAuthStore((state) => state.accessToken);
  const hydrate = useAuthStore((state) => state.hydrate);

  useEffect(() => {
    void hydrate();
  }, [hydrate]);

  return (
    <>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/services" element={<Services />} />
        <Route path="/about" element={<About />} />
        <Route path="/contact" element={<Contact />} />
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="/admin" element={<AdminDashboard accessToken={accessToken} />} />
      </Routes>
      <ChatWidget accessToken={accessToken} />
    </>
  );
}
