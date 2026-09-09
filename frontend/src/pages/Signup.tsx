import { type FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import SiteLayout from "@/components/layout/SiteLayout";
import { usePageTitle } from "@/hooks/usePageTitle";
import { ApiError } from "@/lib/api-client";
import { useAuthStore } from "@/store/auth";

export default function Signup() {
  usePageTitle("Create Account");
  const navigate = useNavigate();
  const signup = useAuthStore((state) => state.signup);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await signup({ email, password, full_name: fullName });
      navigate("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't create your account. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <SiteLayout>
      <section className="mx-auto max-w-md px-6 py-16">
        <h1 className="font-display text-4xl text-neutral-900">Create Account</h1>
        <p className="mt-3 text-neutral-600">Sign up to book appointments and chat with our booking assistant.</p>

        <form onSubmit={(event) => void handleSubmit(event)} className="mt-8 space-y-4">
          <div>
            <label htmlFor="signup-name" className="text-sm font-medium text-neutral-700">
              Full name
            </label>
            <input
              id="signup-name"
              type="text"
              required
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
              className="mt-1 w-full rounded-lg border border-neutral-300 px-3 py-2 text-sm focus:border-brand focus:outline-none"
            />
          </div>
          <div>
            <label htmlFor="signup-email" className="text-sm font-medium text-neutral-700">
              Email
            </label>
            <input
              id="signup-email"
              type="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="mt-1 w-full rounded-lg border border-neutral-300 px-3 py-2 text-sm focus:border-brand focus:outline-none"
            />
          </div>
          <div>
            <label htmlFor="signup-password" className="text-sm font-medium text-neutral-700">
              Password
            </label>
            <input
              id="signup-password"
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="mt-1 w-full rounded-lg border border-neutral-300 px-3 py-2 text-sm focus:border-brand focus:outline-none"
            />
            <p className="mt-1 text-xs text-neutral-400">At least 8 characters.</p>
          </div>

          {error && <p className="text-sm text-red-600">{error}</p>}

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full rounded-full bg-brand px-6 py-3 text-sm font-semibold text-white hover:bg-brand-light disabled:opacity-60"
          >
            {isSubmitting ? "Creating account…" : "Create Account"}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-neutral-600">
          Already have an account?{" "}
          <Link to="/login" className="font-medium text-brand hover:underline">
            Sign in
          </Link>
        </p>
      </section>
    </SiteLayout>
  );
}
