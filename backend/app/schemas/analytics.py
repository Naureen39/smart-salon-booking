import uuid
from datetime import date, datetime

from pydantic import BaseModel


class OverviewStats(BaseModel):
    period_days: int
    total_bookings: int
    no_show_rate: float
    revenue_at_risk_cents: int
    avg_lead_time_hours: float


class DailyStatsPoint(BaseModel):
    date: date
    total_bookings: int
    no_show_count: int
    no_show_rate: float
    revenue_cents: int


class ServicePopularity(BaseModel):
    service_id: uuid.UUID
    service_name: str
    bookings: int
    revenue_cents: int


class StaffUtilization(BaseModel):
    staff_id: uuid.UUID
    staff_title: str | None
    booked_hours: float
    available_hours: float


class ChannelBreakdown(BaseModel):
    web: int
    chat: int
    voice: int
    admin: int


class AtRiskAppointment(BaseModel):
    appointment_id: uuid.UUID
    client_name: str
    client_email: str
    service_name: str
    scheduled_start: datetime
    no_show_risk_score: float


class LlmUsagePoint(BaseModel):
    provider: str
    date: date
    total_calls: int
    total_tokens_in: int
    total_tokens_out: int
    success_count: int
