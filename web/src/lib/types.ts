/** Shared API types (mirrors the FastAPI response shapes). */

export type SimSnapshot = {
  t: number;
  x: number;
  y: number;
  z: number;
  heading_deg: number;
  swing_deg: number;
  phase: string;
  battery_pct: number;
  charging: boolean;
  docked: boolean;
  net_buoyancy_gf: number;
  helium_level_pct: number;
  retries: number;
  plan_name: string;
  waypoint_label: string | null;
};

export type FloorPlan = {
  name: string;
  bounds: [number, number, number, number];
  rooms: { name: string; x: number; y: number; w: number; h: number }[];
  dock: { x: number; y: number; z: number; heading_deg: number };
  waypoints: { label: string; kind: string; x: number; y: number }[];
};

export type BusEvent = {
  topic: string;
  payload: Record<string, unknown>;
  seq: number;
  ts: number;
};

export type Alert = {
  id: number;
  device_id: number;
  level: string;
  state: string;
  reason: string;
  opened_at: string;
  acknowledged_at: string | null;
  acknowledged_by_contact_id: number | null;
  evidence_event_id: number | null;
};

export type Conversation = {
  id: number;
  device_id: number;
  person_id: number | null;
  started_at: string;
  ended_at: string | null;
  mode: string;
  trigger: string;
  mood_note: string | null;
  message_count: number;
};

export type Message = { id: number; ts: string; role: string; content: string };

export type ApiEvent = {
  id: number;
  device_id: number;
  ts: string;
  type: string;
  payload: Record<string, unknown>;
  thumbnail_path: string | null;
};

export type Preset = {
  role: string;
  title: string;
  version: number;
  context: string;
  default_sub: string;
  sub_presets: { key: string; title: string; context: string }[];
};

export type Voice = {
  key: string;
  label: string;
  description: string;
  verified: boolean;
};

export type TierConfig = {
  tier: string;
  provider: string;
  model: string;
  max_tokens: number;
  configured: boolean;
  price_per_mtok: { input: number; output: number } | null;
};

export type ProviderInfo = {
  name: string;
  configured: boolean;
  source: string | null;
};

export type StudioConfig = {
  person_name: string;
  relationship: string | null;
  reminders: { time: string; label: string }[];
  interests: string[];
  tone: string[];
  escalation_note: string | null;
};

export type StudioCurrent = {
  device_id: number;
  person_name: string;
  person_id: number | null;
  role: string;
  sub_preset: string | null;
  voice: string;
  custom_context: string;
  reminders: { time: string; label: string }[];
  interests: string[];
  tone: string[];
  privacy_paused_until: string | null;
  store_transcripts: boolean;
};

export type UsageInfo = {
  pricing_version: string;
  today: { date: string; requests: number; cost_usd: number };
  series: { date: string; requests: number; cost_usd: number }[];
  estimated_monthly_usd: number;
};

export type EngagementDay = {
  date: string;
  sessions: number;
  user_initiated: number;
  minutes: number;
  turns: number;
  user_share?: number;
};

export type Contact = {
  id: number;
  device_id: number;
  name: string;
  phone: string | null;
  relationship_label: string | null;
  order_index: number;
  notify_sms: boolean;
  notify_call: boolean;
};

export type ConsentRecord = {
  id: number;
  device_id: number;
  person_id: number;
  scope: string;
  method: string;
  consenting_party: string;
  is_surrogate: boolean;
  surrogate_relationship: string | null;
  granted: boolean;
  revoked_at: string | null;
};

export type Device = {
  id: number;
  name: string;
  mode: string;
  store_transcripts: boolean;
  is_active: boolean;
};

export type ScheduleEntry = {
  id: number;
  device_id: number;
  time_of_day: string;
  label: string | null;
  enabled: boolean;
};

export type NextCheckin = { time: string; at: string; times: string[] };

export type EngagementResponse = {
  synthetic: boolean;
  label?: string;
  days: number;
  series: EngagementDay[];
};

export type AdherenceSummary = {
  synthetic: boolean;
  label?: string;
  window_days: number;
  delivered: number;
  acknowledged: number;
  completed: number;
  missed: number;
  completion_rate: number | null;
  avg_prompts_required: number | null;
  has_data: boolean;
};

export type HumanContactSummary = {
  synthetic: boolean;
  label?: string;
  window_days: number;
  total: number;
  by_kind: Record<string, number>;
  weekly: { week: string; count: number }[];
};

export type Abandonment = {
  synthetic: boolean;
  label?: string;
  risk: number | null;
  signals: string[];
  has_data: boolean;
};

export type FalseAlarms = {
  synthetic?: boolean;
  label?: string;
  false_alarms_last_7_days: number;
  window_days: number;
};

export type MetricsSummary = {
  synthetic: boolean;
  label?: string;
  false_alarms: FalseAlarms;
  engagement:
    | EngagementResponse
    | { sessions_7d: number; user_initiated_7d: number };
  human_contact: HumanContactSummary;
  abandonment: Abandonment;
};

/** Per-recipient permission matrix (Art. V §4): recipient → scope → allowed. */
export type PermissionMatrix = Record<string, Record<string, boolean>>;
