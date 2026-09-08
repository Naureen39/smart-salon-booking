import { apiFetch } from "@/lib/api-client";

export interface OverviewStats {
  period_days: number;
  total_bookings: number;
  no_show_rate: number;
  revenue_at_risk_cents: number;
  avg_lead_time_hours: number;
}

export interface DailyStatsPoint {
  date: string;
  total_bookings: number;
  no_show_count: number;
  no_show_rate: number;
  revenue_cents: number;
}

export interface ServicePopularity {
  service_id: string;
  service_name: string;
  bookings: number;
  revenue_cents: number;
}

export interface StaffUtilization {
  staff_id: string;
  staff_title: string | null;
  booked_hours: number;
  available_hours: number;
}

export interface ChannelBreakdown {
  web: number;
  chat: number;
  voice: number;
  admin: number;
}

export interface AtRiskAppointment {
  appointment_id: string;
  client_name: string;
  client_email: string;
  service_name: string;
  scheduled_start: string;
  no_show_risk_score: number;
}

export interface LlmUsagePoint {
  provider: string;
  date: string;
  total_calls: number;
  total_tokens_in: number;
  total_tokens_out: number;
  success_count: number;
}

export function getOverview(accessToken: string, days = 30): Promise<OverviewStats> {
  return apiFetch<OverviewStats>(`/api/v1/admin/overview?days=${days}`, undefined, accessToken);
}

export function getBookingsOverTime(accessToken: string, days = 30): Promise<DailyStatsPoint[]> {
  return apiFetch<DailyStatsPoint[]>(`/api/v1/admin/bookings-over-time?days=${days}`, undefined, accessToken);
}

export function getServicePopularity(accessToken: string, days = 30): Promise<ServicePopularity[]> {
  return apiFetch<ServicePopularity[]>(`/api/v1/admin/service-popularity?days=${days}`, undefined, accessToken);
}

export function getStaffUtilization(accessToken: string, days = 30): Promise<StaffUtilization[]> {
  return apiFetch<StaffUtilization[]>(`/api/v1/admin/staff-utilization?days=${days}`, undefined, accessToken);
}

export function getChannelBreakdown(accessToken: string, days = 30): Promise<ChannelBreakdown> {
  return apiFetch<ChannelBreakdown>(`/api/v1/admin/channel-breakdown?days=${days}`, undefined, accessToken);
}

export function getAtRiskAppointments(accessToken: string, limit = 20): Promise<AtRiskAppointment[]> {
  return apiFetch<AtRiskAppointment[]>(`/api/v1/admin/at-risk-appointments?limit=${limit}`, undefined, accessToken);
}

export function getLlmUsage(accessToken: string, days = 7): Promise<LlmUsagePoint[]> {
  return apiFetch<LlmUsagePoint[]>(`/api/v1/admin/llm-usage?days=${days}`, undefined, accessToken);
}

export function sendManualReminder(accessToken: string, appointmentId: string): Promise<{ detail: string }> {
  return apiFetch<{ detail: string }>(
    `/api/v1/admin/appointments/${appointmentId}/send-reminder`,
    { method: "POST" },
    accessToken,
  );
}
