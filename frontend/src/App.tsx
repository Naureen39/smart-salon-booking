import { Route, Routes } from "react-router-dom";

import ChatWidget from "@/components/assistant/ChatWidget";

function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-white">
      <h1 className="font-display text-4xl text-brand">GlowDesk</h1>
      <p className="mt-2 text-neutral-600">AI Salon & Spa Booking Platform</p>
    </main>
  );
}

export default function App() {
  return (
    <>
      <Routes>
        <Route path="/" element={<Home />} />
      </Routes>
      {/* accessToken is null until Phase 10 wires up real auth/login state */}
      <ChatWidget accessToken={null} />
    </>
  );
}
