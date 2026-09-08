import { useCallback, useEffect, useState } from "react";

import {
  type AtRiskAppointment,
  type ChannelBreakdown,
  type DailyStatsPoint,
  type LlmUsagePoint,
  type OverviewStats,
  type ServicePopularity,
  type StaffUtilization,
  getAtRiskAppointments,
  getBookingsOverTime,
  getChannelBreakdown,
  getLlmUsage,
  getOverview,
  getServicePopularity,
  getStaffUtilization,
} from "@/lib/analytics-api";

export function useAdminDashboard(accessToken: string | null) {
  const [overview, setOverview] = useState<OverviewStats | null>(null);
  const [bookingsOverTime, setBookingsOverTime] = useState<DailyStatsPoint[]>([]);
  const [servicePopularity, setServicePopularity] = useState<ServicePopularity[]>([]);
  const [staffUtilization, setStaffUtilization] = useState<StaffUtilization[]>([]);
  const [channelBreakdown, setChannelBreakdown] = useState<ChannelBreakdown | null>(null);
  const [atRiskAppointments, setAtRiskAppointments] = useState<AtRiskAppointment[]>([]);
  const [llmUsage, setLlmUsage] = useState<LlmUsagePoint[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!accessToken) return;
    setIsLoading(true);
    setError(null);
    try {
      const [overviewData, bookingsData, serviceData, staffData, channelData, atRiskData, llmData] =
        await Promise.all([
          getOverview(accessToken),
          getBookingsOverTime(accessToken),
          getServicePopularity(accessToken),
          getStaffUtilization(accessToken),
          getChannelBreakdown(accessToken),
          getAtRiskAppointments(accessToken),
          getLlmUsage(accessToken),
        ]);
      setOverview(overviewData);
      setBookingsOverTime(bookingsData);
      setServicePopularity(serviceData);
      setStaffUtilization(staffData);
      setChannelBreakdown(channelData);
      setAtRiskAppointments(atRiskData);
      setLlmUsage(llmData);
    } catch {
      setError("Couldn't load dashboard data.");
    } finally {
      setIsLoading(false);
    }
  }, [accessToken]);

  useEffect(() => {
    void load();
  }, [load]);

  return {
    overview,
    bookingsOverTime,
    servicePopularity,
    staffUtilization,
    channelBreakdown,
    atRiskAppointments,
    llmUsage,
    isLoading,
    error,
    refresh: load,
  };
}
