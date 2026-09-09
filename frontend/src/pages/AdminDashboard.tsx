import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useAdminDashboard } from "@/hooks/useAdminDashboard";
import { sendManualReminder } from "@/lib/analytics-api";

interface AdminDashboardProps {
  accessToken: string | null;
}

function formatCents(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}

function OverviewCard({ label, value, subtext }: { label: string; value: string; subtext?: string }) {
  return (
    <div className="rounded-xl border border-neutral-200 bg-white p-4 shadow-sm">
      <p className="text-xs font-medium uppercase tracking-wide text-neutral-500">{label}</p>
      <p className="mt-1 font-display text-2xl text-brand">{value}</p>
      {subtext && <p className="mt-1 text-xs text-neutral-400">{subtext}</p>}
    </div>
  );
}

export default function AdminDashboard({ accessToken }: AdminDashboardProps) {
  const {
    overview,
    bookingsOverTime,
    servicePopularity,
    staffUtilization,
    channelBreakdown,
    atRiskAppointments,
    llmUsage,
    isLoading,
    error,
    refresh,
  } = useAdminDashboard(accessToken);
  const [reminderStatus, setReminderStatus] = useState<Record<string, string>>({});

  if (!accessToken) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-neutral-50 p-6 text-center text-neutral-600">
        Please sign in as an admin or staff member to view the dashboard.
      </main>
    );
  }

  const handleSendReminder = async (appointmentId: string) => {
    setReminderStatus((prev) => ({ ...prev, [appointmentId]: "sending" }));
    try {
      await sendManualReminder(accessToken, appointmentId);
      setReminderStatus((prev) => ({ ...prev, [appointmentId]: "sent" }));
    } catch {
      setReminderStatus((prev) => ({ ...prev, [appointmentId]: "error" }));
    }
  };

  return (
    <main className="min-h-screen bg-neutral-50 p-6">
      <div className="mx-auto max-w-6xl space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="font-display text-3xl text-brand">GlowDesk Analytics</h1>
          <button
            type="button"
            onClick={() => void refresh()}
            disabled={isLoading}
            className="rounded-full border border-brand px-4 py-2 text-sm font-medium text-brand hover:bg-brand hover:text-white disabled:opacity-40"
          >
            {isLoading ? "Loading…" : "Refresh"}
          </button>
        </div>

        {error && <p className="rounded-lg bg-red-50 p-3 text-sm text-red-600">{error}</p>}

        {overview && (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <OverviewCard label="Bookings" value={String(overview.total_bookings)} subtext={`last ${overview.period_days}d`} />
            <OverviewCard label="No-show rate" value={`${(overview.no_show_rate * 100).toFixed(1)}%`} />
            <OverviewCard label="Revenue at risk" value={formatCents(overview.revenue_at_risk_cents)} />
            <OverviewCard label="Avg lead time" value={`${overview.avg_lead_time_hours.toFixed(1)}h`} />
          </div>
        )}

        {channelBreakdown && (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <OverviewCard label="Web" value={String(channelBreakdown.web)} />
            <OverviewCard label="Chat" value={String(channelBreakdown.chat)} />
            <OverviewCard label="Voice" value={String(channelBreakdown.voice)} />
            <OverviewCard label="Admin" value={String(channelBreakdown.admin)} />
          </div>
        )}

        <div className="grid gap-6 lg:grid-cols-2">
          <section className="rounded-xl border border-neutral-200 bg-white p-4 shadow-sm">
            <h2 className="mb-3 font-display text-lg text-neutral-800">Bookings over time</h2>
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={bookingsOverTime}>
                <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Line type="monotone" dataKey="total_bookings" stroke="#0f3d2e" strokeWidth={2} dot={false} name="Bookings" />
                <Line type="monotone" dataKey="no_show_count" stroke="#c9a24b" strokeWidth={2} dot={false} name="No-shows" />
              </LineChart>
            </ResponsiveContainer>
          </section>

          <section className="rounded-xl border border-neutral-200 bg-white p-4 shadow-sm">
            <h2 className="mb-3 font-display text-lg text-neutral-800">Service popularity</h2>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={servicePopularity}>
                <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
                <XAxis dataKey="service_name" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="bookings" fill="#0f3d2e" name="Bookings" />
              </BarChart>
            </ResponsiveContainer>
          </section>

          <section className="rounded-xl border border-neutral-200 bg-white p-4 shadow-sm">
            <h2 className="mb-3 font-display text-lg text-neutral-800">Staff utilization</h2>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={staffUtilization}>
                <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
                <XAxis dataKey="staff_title" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="booked_hours" fill="#0f3d2e" name="Booked hrs" />
                <Bar dataKey="available_hours" fill="#c9a24b" name="Available hrs" />
              </BarChart>
            </ResponsiveContainer>
          </section>

          <section className="rounded-xl border border-neutral-200 bg-white p-4 shadow-sm">
            <h2 className="mb-3 font-display text-lg text-neutral-800">LLM usage</h2>
            <div className="max-h-60 overflow-y-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="text-xs uppercase text-neutral-500">
                    <th className="pb-2">Provider</th>
                    <th className="pb-2">Date</th>
                    <th className="pb-2">Calls</th>
                    <th className="pb-2">Tokens in/out</th>
                    <th className="pb-2">Success</th>
                  </tr>
                </thead>
                <tbody>
                  {llmUsage.map((row) => (
                    <tr key={`${row.provider}-${row.date}`} className="border-t border-neutral-100">
                      <td className="py-1">{row.provider}</td>
                      <td className="py-1">{row.date}</td>
                      <td className="py-1">{row.total_calls}</td>
                      <td className="py-1">
                        {row.total_tokens_in}/{row.total_tokens_out}
                      </td>
                      <td className="py-1">{row.success_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </div>

        <section className="rounded-xl border border-neutral-200 bg-white p-4 shadow-sm">
          <h2 className="mb-3 font-display text-lg text-neutral-800">At-risk upcoming appointments</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="text-xs uppercase text-neutral-500">
                  <th className="pb-2">Client</th>
                  <th className="pb-2">Service</th>
                  <th className="pb-2">When</th>
                  <th className="pb-2">Risk</th>
                  <th className="pb-2">Action</th>
                </tr>
              </thead>
              <tbody>
                {atRiskAppointments.map((appointment) => (
                  <tr key={appointment.appointment_id} className="border-t border-neutral-100">
                    <td className="py-2">
                      {appointment.client_name}
                      <div className="text-xs text-neutral-400">{appointment.client_email}</div>
                    </td>
                    <td className="py-2">{appointment.service_name}</td>
                    <td className="py-2">{new Date(appointment.scheduled_start).toLocaleString()}</td>
                    <td className="py-2">
                      <span
                        className={
                          appointment.no_show_risk_score > 0.6
                            ? "rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700"
                            : appointment.no_show_risk_score >= 0.3
                              ? "rounded-full bg-yellow-100 px-2 py-0.5 text-xs font-medium text-yellow-700"
                              : "rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700"
                        }
                      >
                        {(appointment.no_show_risk_score * 100).toFixed(0)}%
                      </span>
                    </td>
                    <td className="py-2">
                      <button
                        type="button"
                        onClick={() => void handleSendReminder(appointment.appointment_id)}
                        disabled={reminderStatus[appointment.appointment_id] === "sending"}
                        className="rounded-full border border-brand px-3 py-1 text-xs font-medium text-brand hover:bg-brand hover:text-white disabled:opacity-40"
                      >
                        {reminderStatus[appointment.appointment_id] === "sent"
                          ? "Sent ✓"
                          : reminderStatus[appointment.appointment_id] === "error"
                            ? "Failed, retry"
                            : "Send reminder"}
                      </button>
                    </td>
                  </tr>
                ))}
                {atRiskAppointments.length === 0 && (
                  <tr>
                    <td colSpan={5} className="py-4 text-center text-neutral-400">
                      No at-risk upcoming appointments.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </main>
  );
}
