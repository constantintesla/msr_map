const API_BASE = import.meta.env.VITE_API_URL || '';

export interface StatusData {
  game_status: string;
  current_stage: number;
  stages: Array<{
    stage: number;
    label: string;
    points_count: number;
    caches_count: number;
  }>;
  score_a?: number | null;
  score_b?: number | null;
  points: Array<{
    id: number;
    name: string;
    lat: number;
    lon: number;
    side: string | null;
    held_by: string | null;
    held_by_user_id?: number | null;
    hold_started_at: string | null;
    last_ping_at?: string | null;
    hold_ready?: boolean;
    hold_elapsed_sec?: number;
    destroyed?: boolean;
    destroyed_by_side?: string | null;
    admin_confirmed?: boolean;
    pending_admin?: boolean;
    kt_number?: number | null;
    stage1_capturable?: boolean;
    entry_url?: string | null;
  }>;
  caches: Array<{
    id: number;
    name: string;
    lat: number;
    lon: number;
    team_side: string | null;
    cache_kind: string;
    destroyed: boolean;
    destroyed_by_side: string | null;
    delivered: boolean;
    delivered_by_side: string | null;
    held_by?: string | null;
    hold_started_at?: string | null;
    hold_ready?: boolean;
    hold_elapsed_sec?: number;
    admin_confirmed?: boolean;
    pending_admin?: boolean;
    delivery_reported?: boolean;
    pending_delivery_admin?: boolean;
    enabled?: boolean;
    stage2_issued?: boolean;
    stage2_active?: boolean;
    loot_variant?: string;
    code_verified?: boolean;
    entry_url?: string | null;
  }>;
  landmarks: Array<{
    id: number;
    name: string;
    lat: number;
    lon: number;
    kind: string;
    team_side: string;
  }>;
  capture_radius_m: number;
  disable_capture_distance: boolean;
  gps_accuracy_bonus_max_m: number;
  gps_min_accuracy_for_capture_m: number;
  gps_lat_offset: number;
  gps_lon_offset: number;
  stage1_recapturable: boolean;
  point_capture_seconds: number;
  point_hold_ping_seconds: number;
  post_hold_seconds: number;
  post_hold_ping_seconds: number;
  hold_deadman_seconds: number;
  stage2_issue_interval_minutes?: number;
  stage2_issue_mode?: string;
  stage2_next_issue_at?: string | null;
  stage2_enabled?: boolean;
  stage2_start_at?: string | null;
  stage1_phase?: string | null;
  stage1_current_slot?: number | null;
  stage1_slot_count?: number;
  stage1_slot_ends_at?: string | null;
  stage1_active_kt_numbers?: number[];
  updated_at: string;
}

export interface AdminEvent {
  id: number;
  created_at: string;
  event_type: string;
  summary: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user_id: number;
  role: string;
  side: string | null;
  point_id: number | null;
  cache_id: number | null;
  lpd_channel?: number | null;
  lpd_frequency_mhz?: number | null;
  lpd_label?: string | null;
  faction_id?: number | null;
  faction_code?: string | null;
  faction_name?: string | null;
}

export interface GameSettings {
  engineers_per_side_a: number;
  engineers_per_side_b: number;
  engineers_count_a: number;
  engineers_count_b: number;
  capture_radius_m: number;
  disable_capture_distance: boolean;
  gps_accuracy_bonus_max_m: number;
  gps_min_accuracy_for_capture_m: number;
  gps_lat_offset: number;
  gps_lon_offset: number;
  stage1_recapturable: boolean;
  point_capture_seconds: number;
  point_hold_ping_seconds: number;
  post_hold_seconds: number;
  post_hold_ping_seconds: number;
  stage2_issue_interval_minutes: number;
  stage2_issue_mode: string;
  stage2_enabled?: boolean;
  stage2_start_at?: string | null;
  stage1_slot_minutes: number;
  stage1_hold_slots: number[][];
}

export interface Stage2Assignment {
  id: number;
  cache_id: number;
  cache_name: string;
  assigned_at: string;
  round_number: number;
  destroyed: boolean;
  destroyed_by_side: string | null;
  delivered: boolean;
  delivered_by_side: string | null;
}

export interface LpdChannel {
  channel: number;
  frequency_mhz: number;
}

export interface EngineerPoolItem {
  id: number;
  username: string;
  side: string;
  password_hint: string;
  lpd_channel: number | null;
  lpd_frequency_mhz: number | null;
  lpd_label: string | null;
}

export interface EngineerProfile {
  username: string;
  side: string;
  lpd_channel: number | null;
  lpd_frequency_mhz: number | null;
  lpd_label: string | null;
  point_id: number | null;
  cache_id: number | null;
}

function authHeaders(): HeadersInit {
  const token = localStorage.getItem('token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function requestHasAuthHeader(headers: HeadersInit | undefined): boolean {
  if (!headers) return false;
  if (headers instanceof Headers) return headers.has('Authorization');
  if (Array.isArray(headers)) {
    return headers.some(([key]) => key.toLowerCase() === 'authorization');
  }
  return Object.keys(headers as Record<string, string>).some((key) => key.toLowerCase() === 'authorization');
}

function clearSessionAndGoLogin(): void {
  localStorage.removeItem('token');
  localStorage.removeItem('role');
  localStorage.removeItem('side');
  localStorage.removeItem('username');
  localStorage.removeItem('user_id');
  if (!window.location.hash.startsWith('#/login')) {
    window.location.replace(`${window.location.pathname}${window.location.search}#/login`);
  }
}

async function authFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const res = await fetch(input, init);
  if (res.status === 401 && requestHasAuthHeader(init?.headers)) {
    clearSessionAndGoLogin();
  }
  return res;
}

export async function login(username: string, password: string): Promise<LoginResponse> {
  const res = await authFetch(`${API_BASE}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) throw new Error('Ошибка входа');
  return res.json();
}

export interface CommanderFeedItem {
  id: number;
  created_at: string;
  event_type: string;
  text: string;
  is_broadcast: boolean;
}

export interface Stage2ActiveLoot {
  cache_id: number;
  name: string;
  lat: number;
  lon: number;
  code: string;
  loot_variant: string;
  url: string;
}

export interface CommanderStatusData extends StatusData {
  viewer_side: string;
  side_label: string;
  stage2_active_loot?: Stage2ActiveLoot | null;
}

export interface MapGridData {
  north: number;
  south: number;
  east: number;
  west: number;
  image_url: string;
}

export async function fetchCommanderStatus(): Promise<CommanderStatusData> {
  const res = await authFetch(`${API_BASE}/api/commander/status`, { headers: authHeaders() });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || 'Ошибка загрузки статуса');
  }
  return res.json();
}

export async function fetchCommanderFeed(): Promise<{ items: CommanderFeedItem[] }> {
  const res = await authFetch(`${API_BASE}/api/commander/feed`, { headers: authHeaders() });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || 'Ошибка загрузки ленты');
  }
  return res.json();
}

export async function adminBroadcast(message: string, targetSide: 'A' | 'B' | 'ALL') {
  const res = await authFetch(`${API_BASE}/api/admin/broadcast`, {
    method: 'POST',
    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, target_side: targetSide }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || 'Не удалось отправить');
  }
  return res.json() as Promise<{ ok: boolean; message: string }>;
}

export async function fetchStatus(): Promise<StatusData> {
  const res = await authFetch(`${API_BASE}/api/status`, { headers: authHeaders() });
  if (!res.ok) throw new Error('Ошибка загрузки статуса');
  return res.json();
}

export async function fetchMapGrid(): Promise<MapGridData | null> {
  const res = await authFetch(`${API_BASE}/api/map/grid`);
  if (!res.ok) throw new Error('Ошибка загрузки сетки');
  const data = await res.json();
  return data as MapGridData | null;
}

export async function fetchAdminStatus(): Promise<StatusData> {
  const res = await authFetch(`${API_BASE}/api/admin/status`, { headers: authHeaders() });
  if (!res.ok) throw new Error('Ошибка загрузки статуса');
  return res.json();
}

export interface SideScoreBreakdown {
  hold: number;
  captures: number;
  loot_breach: number;
  loot_deliver: number;
  posts: number;
  caches: number;
}

export interface ScoreBreakdownData {
  score_a?: number | null;
  score_b?: number | null;
  breakdown_a: SideScoreBreakdown;
  breakdown_b: SideScoreBreakdown;
}

export async function fetchScoreBreakdown(): Promise<ScoreBreakdownData> {
  const res = await authFetch(`${API_BASE}/api/admin/scores/breakdown`, { headers: authHeaders() });
  if (!res.ok) throw new Error('Ошибка загрузки счёта');
  return res.json();
}

export async function resolveQrToken(token: string): Promise<{ kind: 'point' | 'cache'; id: number }> {
  const res = await authFetch(`${API_BASE}/api/public/qr/${encodeURIComponent(token)}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || 'Ссылка недействительна');
  }
  return res.json();
}

export async function syncHoldPoint(pointId: number) {
  const res = await authFetch(`${API_BASE}/api/hold/point/${pointId}`, { headers: authHeaders() });
  if (!res.ok) throw new Error('Ошибка проверки удержания');
  return res.json() as Promise<{
    ok: boolean;
    active: boolean;
    side?: string;
    user_id?: number;
    last_ping_at?: string;
    hold_ready?: boolean;
    hold_elapsed_sec?: number;
    hold_deadman_seconds: number;
  }>;
}

async function holdApiError(res: Response, fallback: string): Promise<never> {
  const err = await res.json().catch(() => ({}));
  const detail = (err as { detail?: string | Array<{ msg?: string }> }).detail;
  const message =
    typeof detail === 'string'
      ? detail
      : Array.isArray(detail)
        ? detail.map((d) => d.msg).filter(Boolean).join(', ') || fallback
        : fallback;
  throw new Error(message);
}

export async function holdConfirm(pointId: number, side: string) {
  const res = await authFetch(`${API_BASE}/api/hold/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ point_id: pointId, side }),
  });
  if (!res.ok) await holdApiError(res, 'Ошибка подтверждения удержания');
  return res.json() as Promise<{
    ok: boolean;
    session_id: number;
    last_ping_at: string;
    hold_ready?: boolean;
    hold_elapsed_sec?: number;
    hold_deadman_seconds: number;
  }>;
}

export async function holdLeave(pointId: number, side: string) {
  const res = await authFetch(`${API_BASE}/api/hold/leave`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ point_id: pointId, side }),
  });
  if (!res.ok) throw new Error('Ошибка сброса удержания');
  return res.json();
}

export async function holdCacheConfirm(cacheId: number, side: string) {
  const res = await authFetch(`${API_BASE}/api/hold/cache/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ cache_id: cacheId, side }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || 'Ошибка удержания схрона');
  }
  return res.json() as Promise<{
    ok: boolean;
    hold_ready: boolean;
    hold_elapsed_sec: number;
  }>;
}

export async function holdCacheLeave(cacheId: number, side: string) {
  const res = await authFetch(`${API_BASE}/api/hold/cache/leave`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ cache_id: cacheId, side }),
  });
  if (!res.ok) throw new Error('Ошибка сброса удержания схрона');
  return res.json();
}

export async function adminConfirmCache(cacheId: number, opts?: { side?: 'A' | 'B' }) {
  const res = await authFetch(`${API_BASE}/api/admin/cache/${cacheId}/confirm`, {
    method: 'POST',
    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify(opts?.side ? { side: opts.side } : {}),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || 'Ошибка подтверждения');
  }
  return res.json() as Promise<{ ok: boolean; message: string }>;
}

export async function adminConfirmDelivery(cacheId: number, opts?: { side?: 'A' | 'B' }) {
  const res = await authFetch(`${API_BASE}/api/admin/cache/${cacheId}/confirm-delivery`, {
    method: 'POST',
    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify(opts?.side ? { side: opts.side } : {}),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || 'Ошибка подтверждения доставки');
  }
  return res.json() as Promise<{ ok: boolean; message: string }>;
}

export async function adminConfirmPoint(pointId: number) {
  const res = await authFetch(`${API_BASE}/api/admin/point/${pointId}/confirm`, {
    method: 'POST',
    headers: authHeaders(),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || 'Ошибка подтверждения');
  }
  return res.json() as Promise<{ ok: boolean; message: string }>;
}

export async function submitPostFilmReport(
  pointId: number,
  side: string,
  lat: number,
  lon: number,
  file: File,
) {
  const form = new FormData();
  form.append('point_id', String(pointId));
  form.append('side', side);
  form.append('lat', String(lat));
  form.append('lon', String(lon));
  form.append('file', file);
  const res = await authFetch(`${API_BASE}/api/point/post-film-report`, {
    method: 'POST',
    headers: authHeaders(),
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || 'Ошибка отправки видеоотчёта');
  }
  return res.json() as Promise<{ ok: boolean; bonus: number; message?: string }>;
}

export async function detonatePoint(pointId: number, code: string, side: string) {
  const res = await authFetch(`${API_BASE}/api/point/detonate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ point_id: pointId, code, side }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || 'Ошибка детонации');
  }
  return res.json() as Promise<{ ok: boolean; bonus: number; message?: string }>;
}

export async function submitBreachCode(
  cacheId: number,
  code: string,
  side: string,
  qrToken: string,
  lat?: number,
  lon?: number,
  accuracy?: number,
) {
  const res = await authFetch(`${API_BASE}/api/cache/breach-code`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ cache_id: cacheId, code, side, qr_token: qrToken, lat, lon, accuracy }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || 'Неверный код');
  }
  return res.json() as Promise<{ ok: boolean; message?: string; next_step?: string }>;
}

export async function submitUnlockCode(
  cacheId: number,
  code: string,
  side: string,
  qrToken: string,
  lat?: number,
  lon?: number,
  accuracy?: number,
) {
  const res = await authFetch(`${API_BASE}/api/cache/unlock-code`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ cache_id: cacheId, code, side, qr_token: qrToken, lat, lon, accuracy }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || 'Неверный код');
  }
  return res.json() as Promise<{ ok: boolean; message?: string; next_step?: string }>;
}

export async function submitFilmReport(
  cacheId: number,
  side: string,
  lat: number,
  lon: number,
  qrToken: string,
  file: File,
) {
  const form = new FormData();
  form.append('cache_id', String(cacheId));
  form.append('side', side);
  form.append('lat', String(lat));
  form.append('lon', String(lon));
  form.append('qr_token', qrToken);
  form.append('file', file);
  const res = await authFetch(`${API_BASE}/api/cache/film-report`, {
    method: 'POST',
    headers: authHeaders(),
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || 'Ошибка отправки видеоотчёта');
  }
  return res.json() as Promise<{ ok: boolean; bonus: number; message?: string; next_step?: string }>;
}

export async function detonateCache(cacheId: number, code: string, side: string) {
  const res = await authFetch(`${API_BASE}/api/cache/detonate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ cache_id: cacheId, code, side }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Ошибка детонации');
  }
  return res.json() as Promise<{ ok: boolean; bonus: number; message?: string; next_step?: string }>;
}

export async function submitDeliverReport(
  cacheId: number,
  side: string,
  lat: number,
  lon: number,
  qrToken: string,
  file: File,
) {
  const form = new FormData();
  form.append('cache_id', String(cacheId));
  form.append('side', side);
  form.append('lat', String(lat));
  form.append('lon', String(lon));
  form.append('qr_token', qrToken);
  form.append('file', file);
  const res = await authFetch(`${API_BASE}/api/cache/deliver-report`, {
    method: 'POST',
    headers: authHeaders(),
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || 'Ошибка отправки фотоотчёта');
  }
  return res.json() as Promise<{ ok: boolean; message?: string }>;
}

export async function deliverLoot(cacheId: number, side: string, lat: number, lon: number) {
  const res = await authFetch(`${API_BASE}/api/cache/deliver`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ cache_id: cacheId, side, lat, lon }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Ошибка доставки');
  }
  return res.json() as Promise<{ ok: boolean; bonus: number; message: string }>;
}

export async function beginPointCapture(
  pointId: number,
  code: string,
  side: string,
  lat: number,
  lon: number,
  accuracy?: number,
) {
  const res = await authFetch(`${API_BASE}/api/point/begin-capture`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ point_id: pointId, code, side, lat, lon, accuracy }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || 'Ошибка начала захвата');
  }
  return res.json() as Promise<{
    ok: boolean;
    last_ping_at: string;
    hold_ready?: boolean;
    hold_elapsed_sec?: number;
    hold_deadman_seconds: number;
    message?: string;
  }>;
}

export async function fetchStage1Mission() {
  const res = await authFetch(`${API_BASE}/api/admin/stage1/mission`, { headers: authHeaders() });
  if (!res.ok) throw new Error('Ошибка загрузки КТ');
  return res.json() as Promise<
    Array<{ id: number; name: string; lat: number; lon: number; code: string; url: string; enabled?: boolean }>
  >;
}

export async function updateStage1Code(pointId: number, code: string) {
  const res = await authFetch(`${API_BASE}/api/admin/stage1/mission/${pointId}`, {
    method: 'PATCH',
    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ code }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || 'Не удалось сохранить код');
  }
  return res.json() as Promise<{ id: number; name: string; lat: number; lon: number; code: string; url: string }>;
}

export async function fetchStage2Mission() {
  const res = await authFetch(`${API_BASE}/api/admin/stage2/mission`, { headers: authHeaders() });
  if (!res.ok) throw new Error('Ошибка загрузки миссии');
  return res.json() as Promise<
    Array<{ id: number; name: string; lat: number; lon: number; code: string; url: string; enabled?: boolean }>
  >;
}

export async function updateStage2Mission(
  cacheId: number,
  patch: { code?: string; enabled?: boolean }
) {
  const res = await authFetch(`${API_BASE}/api/admin/stage2/mission/${cacheId}`, {
    method: 'PATCH',
    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || 'Не удалось обновить ящик');
  }
  return res.json() as Promise<{
    id: number;
    name: string;
    lat: number;
    lon: number;
    code: string;
    url: string;
    enabled?: boolean;
  }>;
}

export async function updateStage2Code(cacheId: number, code: string) {
  return updateStage2Mission(cacheId, { code });
}

export async function fetchStage3Mertvyaki() {
  const res = await authFetch(`${API_BASE}/api/admin/stage3/mertvyaki`, { headers: authHeaders() });
  if (!res.ok) throw new Error('Ошибка загрузки мертвяков');
  return res.json() as Promise<
    Array<{ id: number; name: string; lat: number; lon: number; code: string; url: string; enabled: boolean }>
  >;
}

export async function updateMertvyak(cacheId: number, patch: { code?: string; enabled?: boolean }) {
  const res = await authFetch(`${API_BASE}/api/admin/stage3/mertvyaki/${cacheId}`, {
    method: 'PATCH',
    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || 'Не удалось сохранить');
  }
  return res.json() as Promise<{ id: number; name: string; lat: number; lon: number; code: string; url: string; enabled: boolean }>;
}

export interface MapObjectOut {
  id: number;
  name: string;
  lat: number;
  lon: number;
  kind?: string | null;
  stage?: number | null;
  cache_kind?: string | null;
  team_side?: string | null;
}

async function mapEditJson<T>(path: string, method: string, body?: unknown): Promise<T> {
  const res = await authFetch(`${API_BASE}/api/admin${path}`, {
    method,
    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || 'Ошибка редактирования карты');
  }
  return res.json() as Promise<T>;
}

export function updateMapPoint(pointId: number, patch: { lat?: number; lon?: number; name?: string }) {
  return mapEditJson<MapObjectOut>(`/map/points/${pointId}`, 'PATCH', patch);
}

export function createMapPoint(body: { lat: number; lon: number; stage: number; name?: string }) {
  return mapEditJson<MapObjectOut>('/map/points', 'POST', body);
}

export function deleteMapPoint(pointId: number) {
  return mapEditJson<{ ok: boolean; message: string }>(`/map/points/${pointId}`, 'DELETE');
}

export function updateMapCache(
  cacheId: number,
  patch: { lat?: number; lon?: number; name?: string; team_side?: 'A' | 'B' }
) {
  return mapEditJson<MapObjectOut>(`/map/caches/${cacheId}`, 'PATCH', patch);
}

export function createMapCache(body: {
  lat: number;
  lon: number;
  stage: number;
  cache_kind: 'film_loot' | 'post' | 'mertvyak';
  team_side?: 'A' | 'B';
  name?: string;
}) {
  return mapEditJson<MapObjectOut>('/map/caches', 'POST', body);
}

export function deleteMapCache(cacheId: number) {
  return mapEditJson<{ ok: boolean; message: string }>(`/map/caches/${cacheId}`, 'DELETE');
}

export function updateMapLandmark(
  landmarkId: number,
  patch: { lat?: number; lon?: number; name?: string; kind?: 'base' | 'start' | 'base_start'; team_side?: 'A' | 'B' }
) {
  return mapEditJson<MapObjectOut>(`/map/landmarks/${landmarkId}`, 'PATCH', patch);
}

export function createMapLandmark(body: {
  lat: number;
  lon: number;
  kind: 'base' | 'start' | 'base_start';
  team_side: 'A' | 'B';
  name?: string;
}) {
  return mapEditJson<MapObjectOut>('/map/landmarks', 'POST', body);
}

export function deleteMapLandmark(landmarkId: number) {
  return mapEditJson<{ ok: boolean; message: string }>(`/map/landmarks/${landmarkId}`, 'DELETE');
}

export async function fetchAdminEvents(): Promise<AdminEvent[]> {
  const res = await authFetch(`${API_BASE}/api/admin/events`, { headers: authHeaders() });
  if (!res.ok) throw new Error('Ошибка загрузки событий');
  return res.json();
}

export async function exportLogs() {
  const res = await authFetch(`${API_BASE}/api/admin/export/logs`, { headers: authHeaders() });
  if (!res.ok) throw new Error('Ошибка экспорта');
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'event_log.csv.gz';
  a.click();
  URL.revokeObjectURL(url);
}

export async function exportEngineers() {
  const res = await authFetch(`${API_BASE}/api/admin/export/engineers`, { headers: authHeaders() });
  if (!res.ok) throw new Error('Ошибка экспорта списка инженеров');
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'engineers.csv';
  a.click();
  URL.revokeObjectURL(url);
}

export async function wipeAllMapObjects(): Promise<{ ok: boolean; message: string }> {
  const res = await authFetch(`${API_BASE}/api/admin/map/wipe`, {
    method: 'POST',
    headers: authHeaders(),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const detail = (err as { detail?: string }).detail;
    throw new Error(detail || 'Ошибка удаления объектов');
  }
  return res.json();
}

export async function adminAction(path: string): Promise<{ ok: boolean; message: string }> {
  const res = await authFetch(`${API_BASE}/api/admin${path}`, {
    method: 'POST',
    headers: authHeaders(),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const detail = (err as { detail?: string }).detail;
    throw new Error(detail || 'Ошибка админ-действия');
  }
  return res.json();
}

export async function uploadKmz(file: File) {
  const form = new FormData();
  form.append('file', file);
  const res = await authFetch(`${API_BASE}/api/admin/kmz/import`, {
    method: 'POST',
    headers: authHeaders(),
    body: form,
  });
  if (!res.ok) throw new Error('Ошибка импорта KMZ');
  return res.json();
}

export type ChatThread = 'cmd' | 'eng';

export interface ChatMessage {
  id: number;
  created_at: string;
  side: string;
  thread?: string;
  sender_role: string;
  sender_name: string;
  text: string | null;
  media_type: string | null;
  has_media: boolean;
  media_filename: string | null;
  recipient_username?: string | null;
}

export async function fetchChatMessages(
  side?: 'A' | 'B',
  afterId = 0,
  thread: ChatThread = 'cmd'
): Promise<{ side: string; thread: string; items: ChatMessage[] }> {
  const params = new URLSearchParams();
  if (side) params.set('side', side);
  if (afterId > 0) params.set('after_id', String(afterId));
  if (thread) params.set('thread', thread);
  const qs = params.toString();
  const res = await authFetch(`${API_BASE}/api/chat/messages${qs ? `?${qs}` : ''}`, { headers: authHeaders() });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || 'Ошибка чата');
  }
  return res.json();
}

export async function fetchChatRecipients(side?: 'A' | 'B'): Promise<Array<{ username: string }>> {
  const params = side ? `?side=${side}` : '';
  const res = await authFetch(`${API_BASE}/api/chat/recipients${params}`, { headers: authHeaders() });
  if (!res.ok) throw new Error('Ошибка загрузки инженеров');
  return res.json();
}

export async function sendChatMessage(opts: {
  text?: string;
  file?: File | null;
  side?: 'A' | 'B';
  thread?: ChatThread;
  recipient_username?: string | null;
}): Promise<ChatMessage> {
  const form = new FormData();
  if (opts.text) form.append('text', opts.text);
  if (opts.side) form.append('side', opts.side);
  if (opts.thread) form.append('thread', opts.thread);
  if (opts.recipient_username) form.append('recipient_username', opts.recipient_username);
  if (opts.file) form.append('file', opts.file);
  const res = await authFetch(`${API_BASE}/api/chat/messages`, {
    method: 'POST',
    headers: authHeaders(),
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const fallback = res.status === 413 ? 'Файл слишком большой' : 'Не удалось отправить';
    throw new Error(parseApiErrorDetail(err, fallback));
  }
  return res.json();
}

export async function fetchChatMediaBlob(messageId: number): Promise<Blob> {
  const res = await authFetch(`${API_BASE}/api/chat/media/${messageId}`, { headers: authHeaders() });
  if (!res.ok) throw new Error('Медиа недоступно');
  return res.blob();
}

export function getWsUrl(): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = import.meta.env.VITE_WS_HOST || window.location.host;
  const token = localStorage.getItem('token') || '';
  return `${proto}//${host}/ws/admin?token=${encodeURIComponent(token)}`;
}

export function getCommanderWsUrl(): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = import.meta.env.VITE_WS_HOST || window.location.host;
  const token = localStorage.getItem('token') || '';
  return `${proto}//${host}/ws/commander?token=${encodeURIComponent(token)}`;
}

export function getEngineerWsUrl(): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = import.meta.env.VITE_WS_HOST || window.location.host;
  const token = localStorage.getItem('token') || '';
  return `${proto}//${host}/ws/engineer?token=${encodeURIComponent(token)}`;
}

export interface EngineerLocation {
  user_id: number;
  username: string;
  side: string;
  label: string;
  lat: number;
  lon: number;
  accuracy: number;
  updated_at: string;
}

export interface MovementTrackPoint {
  lat: number;
  lon: number;
  accuracy: number;
  recorded_at: string;
}

export interface MovementTrackUser {
  user_id: number;
  username: string;
  side: string;
  label: string;
  points: MovementTrackPoint[];
}

export interface MovementTracksData {
  game_session_id: number;
  game_status: string;
  game_started_at: string | null;
  tracks: MovementTrackUser[];
  total_points: number;
}

export async function fetchMovementTracks(): Promise<MovementTracksData> {
  const res = await authFetch(`${API_BASE}/api/admin/movement-tracks`, { headers: authHeaders() });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || 'Ошибка загрузки треков');
  }
  return res.json();
}

export async function exportMovementTracks() {
  const res = await authFetch(`${API_BASE}/api/admin/export/movement-tracks`, { headers: authHeaders() });
  if (!res.ok) throw new Error('Ошибка экспорта треков');
  const blob = await res.blob();
  const sessionId = res.headers.get('Content-Disposition')?.match(/session_(\d+)/)?.[1] ?? 'current';
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `movement_tracks_session_${sessionId}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export async function pingEngineerLocation(lat: number, lon: number, accuracy: number) {
  const res = await authFetch(`${API_BASE}/api/location/ping`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ lat, lon, accuracy }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || 'Ошибка GPS');
  }
  return res.json();
}

export async function fetchEngineerLocations(side?: 'A' | 'B'): Promise<EngineerLocation[]> {
  const qs = side ? `?side=${side}` : '';
  const res = await authFetch(`${API_BASE}/api/location/engineers${qs}`, { headers: authHeaders() });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || 'Ошибка загрузки позиций');
  }
  return res.json();
}

export async function fetchGameSettings(): Promise<GameSettings> {
  const res = await authFetch(`${API_BASE}/api/admin/settings`, { headers: authHeaders() });
  if (!res.ok) throw new Error('Ошибка загрузки настроек');
  return res.json();
}

export interface Scenario {
  id: number;
  name: string;
  slug: string;
  is_active: boolean;
  created_at: string;
}

export async function fetchScenarios(): Promise<Scenario[]> {
  const res = await authFetch(`${API_BASE}/api/admin/scenarios`, { headers: authHeaders() });
  if (!res.ok) throw new Error('Ошибка загрузки сценариев');
  return res.json();
}

export async function createScenario(name: string): Promise<Scenario> {
  const res = await authFetch(`${API_BASE}/api/admin/scenarios`, {
    method: 'POST',
    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || 'Не удалось создать сценарий');
  }
  return res.json();
}

export async function activateScenario(scenarioId: number): Promise<Scenario> {
  const res = await authFetch(`${API_BASE}/api/admin/scenarios/${scenarioId}/activate`, {
    method: 'POST',
    headers: authHeaders(),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || 'Не удалось переключить сценарий');
  }
  return res.json();
}

export async function archiveScenario(scenarioId: number): Promise<Scenario> {
  const res = await authFetch(`${API_BASE}/api/admin/scenarios/${scenarioId}/archive`, {
    method: 'POST',
    headers: authHeaders(),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || 'Не удалось архивировать сценарий');
  }
  return res.json();
}

const SETTINGS_FIELD_LABELS: Record<string, string> = {
  engineers_per_side_a: 'ЛК (A)',
  engineers_per_side_b: 'СБГ (B)',
  capture_radius_m: 'Радиус захвата',
  point_capture_seconds: 'Время захвата КТ',
  point_hold_ping_seconds: 'Интервал кнопки КТ',
  post_hold_seconds: 'Время удержания поста',
  post_hold_ping_seconds: 'Интервал кнопки поста',
  stage2_issue_interval_minutes: 'Интервал автовыдачи',
  stage2_issue_mode: 'Режим автовыдачи',
  stage1_slot_minutes: 'Слот',
  stage1_hold_slots: 'Наборы КТ по слотам',
};

function parseApiErrorDetail(err: unknown, fallback: string): string {
  const detail = (err as { detail?: unknown }).detail;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) => {
        if (!item || typeof item !== 'object') return null;
        const it = item as { msg?: string };
        return it.msg || null;
      })
      .filter((s): s is string => Boolean(s));
    if (parts.length) return parts.join('; ');
  }
  return fallback;
}

function formatValidationError(err: unknown, fallback: string): string {
  const detail = (err as { detail?: unknown }).detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) => {
        if (!item || typeof item !== 'object') return null;
        const it = item as { loc?: unknown[]; msg?: string };
        const field = Array.isArray(it.loc) ? (it.loc[it.loc.length - 1] as string | number) : '';
        const label = SETTINGS_FIELD_LABELS[String(field)] || String(field || '');
        return label ? `${label}: ${it.msg}` : it.msg;
      })
      .filter((s): s is string => Boolean(s));
    if (parts.length) return parts.join('; ');
  }
  return fallback;
}

export async function updateGameSettings(data: {
  engineers_per_side_a: number;
  engineers_per_side_b: number;
  capture_radius_m: number;
  disable_capture_distance: boolean;
  gps_accuracy_bonus_max_m: number;
  gps_min_accuracy_for_capture_m: number;
  gps_lat_offset: number;
  gps_lon_offset: number;
  stage1_recapturable: boolean;
  point_capture_seconds: number;
  point_hold_ping_seconds?: number;
  post_hold_seconds?: number;
  post_hold_ping_seconds?: number;
  stage2_issue_interval_minutes?: number;
  stage2_issue_mode?: string;
  stage2_start_at?: string | null;
  stage1_slot_minutes?: number;
  stage1_hold_slots?: number[][];
  gps_accuracy_bonus_max_m?: number;
  gps_min_accuracy_for_capture_m?: number;
  gps_lat_offset?: number;
  gps_lon_offset?: number;
}): Promise<GameSettings> {
  const res = await authFetch(`${API_BASE}/api/admin/settings`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(formatValidationError(err, 'Ошибка сохранения настроек'));
  }
  return res.json();
}

export async function calibrateGps(data: {
  true_lat: number;
  true_lon: number;
  measured_lat: number;
  measured_lon: number;
}): Promise<GameSettings> {
  const res = await authFetch(`${API_BASE}/api/admin/gps-calibrate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || 'Ошибка калибровки GPS');
  }
  return res.json();
}

export async function fetchStage2Assignments(): Promise<Stage2Assignment[]> {
  const res = await authFetch(`${API_BASE}/api/admin/stage2/assignments`, { headers: authHeaders() });
  if (!res.ok) throw new Error('Ошибка загрузки выдач');
  return res.json();
}

export async function issueStage2Target(): Promise<{ ok: boolean; message: string }> {
  const res = await authFetch(`${API_BASE}/api/admin/stage2/issue`, {
    method: 'POST',
    headers: authHeaders(),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || 'Не удалось выдать цель');
  }
  return res.json();
}

export async function enableStage2(): Promise<{ ok: boolean; message: string }> {
  const res = await authFetch(`${API_BASE}/api/admin/stage2/enable`, {
    method: 'POST',
    headers: authHeaders(),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || 'Не удалось включить Задачу-2');
  }
  return res.json();
}

export async function startStage1Slot(): Promise<{ ok: boolean; message: string }> {
  const res = await authFetch(`${API_BASE}/api/admin/stage1/start-slot`, {
    method: 'POST',
    headers: authHeaders(),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || 'Ошибка запуска слота');
  }
  return res.json();
}

export async function nextStage1Slot(): Promise<{ ok: boolean; message: string }> {
  const res = await authFetch(`${API_BASE}/api/admin/stage1/next-slot`, {
    method: 'POST',
    headers: authHeaders(),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || 'Ошибка перехода слота');
  }
  return res.json();
}

export async function fetchLpdChannels(): Promise<LpdChannel[]> {
  const res = await authFetch(`${API_BASE}/api/commander/lpd-channels`, { headers: authHeaders() });
  if (!res.ok) throw new Error('Ошибка загрузки LPD');
  return res.json();
}

export async function fetchCommanderEngineers(): Promise<EngineerPoolItem[]> {
  const res = await authFetch(`${API_BASE}/api/commander/engineers`, { headers: authHeaders() });
  if (!res.ok) throw new Error('Ошибка загрузки инженеров');
  return res.json();
}

export async function assignEngineerLpdChannel(
  engineerId: number,
  lpd_channel: number | null
): Promise<EngineerPoolItem> {
  const res = await authFetch(`${API_BASE}/api/commander/engineers/${engineerId}/lpd-channel`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ lpd_channel }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || 'Ошибка назначения канала');
  }
  return res.json();
}

export async function fetchEngineerProfile(): Promise<EngineerProfile> {
  const res = await authFetch(`${API_BASE}/api/engineer/profile`, { headers: authHeaders() });
  if (!res.ok) throw new Error('Ошибка профиля');
  return res.json();
}

export interface FieldOrder {
  id: number;
  created_at: string;
  side: string;
  commander_username: string;
  engineer_username: string;
  target_kind: 'point' | 'cache';
  target_id: number;
  target_name: string;
  target_lat: number;
  target_lon: number;
  note: string | null;
  acknowledged_at: string | null;
  dismissed: boolean;
}

export async function sendFieldOrder(body: {
  engineer_user_id: number;
  target_kind: 'point' | 'cache';
  target_id: number;
  note?: string;
}): Promise<FieldOrder> {
  const res = await authFetch(`${API_BASE}/api/commander/orders`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || 'Ошибка отправки приказа');
  }
  return res.json();
}

export async function fetchActiveFieldOrders(): Promise<FieldOrder[]> {
  const res = await authFetch(`${API_BASE}/api/engineer/orders/active`, { headers: authHeaders() });
  if (!res.ok) return [];
  return res.json();
}

export async function dismissFieldOrder(orderId: number): Promise<FieldOrder | null> {
  const res = await authFetch(`${API_BASE}/api/engineer/orders/${orderId}/dismiss`, {
    method: 'POST',
    headers: authHeaders(),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || 'Ошибка');
  }
  const data = await res.json();
  return (data as { order?: FieldOrder }).order ?? null;
}

export async function fetchCommanderFieldOrders(): Promise<FieldOrder[]> {
  const res = await authFetch(`${API_BASE}/api/commander/orders`, { headers: authHeaders() });
  if (!res.ok) return [];
  return res.json();
}

export async function fetchAdminFieldOrders(side?: 'A' | 'B'): Promise<FieldOrder[]> {
  const qs = side ? `?side=${side}` : '';
  const res = await authFetch(`${API_BASE}/api/admin/orders${qs}`, { headers: authHeaders() });
  if (!res.ok) return [];
  return res.json();
}

// --- Башня: стороны, QR-раскрытие, УР, командирская консоль ---

export interface TowerFactionAdmin {
  id: number;
  code: string;
  name: string;
  kind: string;
  elder_note: string | null;
  elder_photo_url: string | null;
  drop_lat: number | null;
  drop_lon: number | null;
  join_url: string | null;
  qr_url: string | null;
  registered_count: number;
}

export interface TowerCommanderAdmin {
  faction_code: string;
  faction_name: string;
  username: string;
  password: string;
}

export interface TowerUrPointAdmin {
  id: number;
  name: string;
  scanned: boolean;
  qr_url: string | null;
}

export interface TowerUrZoneAdmin {
  id: number;
  name: string;
  status: string;
  hold_ends_at: string | null;
  points: TowerUrPointAdmin[];
}

export interface TowerAdminOverview {
  scenario_id: number;
  factions: TowerFactionAdmin[];
  commanders: TowerCommanderAdmin[];
  ur_zones: TowerUrZoneAdmin[];
  reveal_schedule: string[];
  ur_sync_window_seconds: number;
  ur_hold_seconds: number;
}

async function towerAdminError(res: Response, fallback: string): Promise<never> {
  const err = await res.json().catch(() => ({}));
  throw new Error((err as { detail?: string }).detail || fallback);
}

export async function seedTowerScenario(): Promise<TowerAdminOverview> {
  const res = await authFetch(`${API_BASE}/api/admin/tower/seed`, { method: 'POST', headers: authHeaders() });
  if (!res.ok) await towerAdminError(res, 'Не удалось создать сценарий «Башня»');
  return res.json();
}

export async function fetchTowerAdminOverview(): Promise<TowerAdminOverview | null> {
  const res = await authFetch(`${API_BASE}/api/admin/tower/overview`, { headers: authHeaders() });
  if (res.status === 404) return null;
  if (!res.ok) await towerAdminError(res, 'Ошибка загрузки Башни');
  return res.json();
}

export async function updateTowerFaction(
  factionId: number,
  patch: { elder_note?: string; drop_lat?: number; drop_lon?: number }
): Promise<TowerFactionAdmin> {
  const res = await authFetch(`${API_BASE}/api/admin/tower/factions/${factionId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(patch),
  });
  if (!res.ok) await towerAdminError(res, 'Не удалось сохранить сторону');
  return res.json();
}

export async function resetTowerUrZone(zoneId: number): Promise<{ ok: boolean }> {
  const res = await authFetch(`${API_BASE}/api/admin/tower/ur-zones/${zoneId}/reset`, {
    method: 'POST',
    headers: authHeaders(),
  });
  if (!res.ok) await towerAdminError(res, 'Не удалось сбросить УР');
  return res.json();
}

export async function updateTowerRevealSchedule(thresholds: string[]): Promise<{ ok: boolean }> {
  const res = await authFetch(`${API_BASE}/api/admin/tower/reveal-schedule`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ thresholds }),
  });
  if (!res.ok) await towerAdminError(res, 'Не удалось сохранить расписание');
  return res.json();
}

export interface TowerJoinInfo {
  faction_code: string;
  faction_name: string;
}

export async function fetchTowerJoinInfo(token: string): Promise<TowerJoinInfo> {
  const res = await authFetch(`${API_BASE}/api/public/tower/join/${encodeURIComponent(token)}`);
  if (!res.ok) await towerAdminError(res, 'Ссылка недействительна');
  return res.json();
}

export async function registerTowerAccount(
  token: string,
  callsign: string,
  pin: string
): Promise<LoginResponse> {
  const res = await authFetch(`${API_BASE}/api/public/tower/join/${encodeURIComponent(token)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ callsign, pin }),
  });
  if (!res.ok) await towerAdminError(res, 'Не удалось зарегистрироваться');
  return res.json();
}

export type TowerScanResult =
  | {
      kind: 'village';
      data: {
        target_faction_code: string;
        target_faction_name: string;
        elder_photo_url?: string | null;
        elder_note?: string | null;
        drop_lat?: number | null;
        drop_lon?: number | null;
        cache_targets?: Array<{ name: string; lat: number; lon: number }>;
        revealed_count?: number;
        total_targets?: number;
      };
    }
  | {
      kind: 'ur_zone';
      data: {
        zone_id: number;
        zone_name: string;
        status: 'idle' | 'syncing' | 'holding' | 'captured';
        sync_started_at: string | null;
        hold_started_at: string | null;
        hold_ends_at: string | null;
        captured_at: string | null;
        points: Array<{ id: number; name: string; scanned: boolean }>;
      };
    };

export async function scanTowerToken(token?: string, code?: string): Promise<TowerScanResult> {
  const res = await authFetch(`${API_BASE}/api/tower/scan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ token, code }),
  });
  if (!res.ok) await towerAdminError(res, 'Табличка не найдена');
  return res.json();
}

export interface TowerUrZoneStatus {
  zone_id: number;
  zone_name: string;
  status: 'idle' | 'syncing' | 'holding' | 'captured';
  sync_started_at: string | null;
  hold_started_at: string | null;
  hold_ends_at: string | null;
  captured_at: string | null;
  points: Array<{ id: number; name: string; scanned: boolean }>;
}

export async function fetchTowerStatus(): Promise<{ ur_zones: TowerUrZoneStatus[] }> {
  const res = await authFetch(`${API_BASE}/api/tower/status`, { headers: authHeaders() });
  if (!res.ok) await towerAdminError(res, 'Ошибка загрузки статуса');
  return res.json();
}

export interface TowerChatMessage {
  id: number;
  created_at: string;
  faction_id: number;
  thread: string;
  sender_role: string;
  sender_name: string;
  text: string | null;
  media_type: string | null;
  has_media: boolean;
  media_filename: string | null;
  recipient_username: string | null;
}

export async function fetchTowerChatMessages(
  thread?: 'cmd' | 'eng',
  afterId = 0
): Promise<{ faction_id: number; thread: string; items: TowerChatMessage[] }> {
  const params = new URLSearchParams();
  if (thread) params.set('thread', thread);
  if (afterId > 0) params.set('after_id', String(afterId));
  const qs = params.toString();
  const res = await authFetch(`${API_BASE}/api/tower/chat/messages${qs ? `?${qs}` : ''}`, { headers: authHeaders() });
  if (!res.ok) await towerAdminError(res, 'Ошибка чата');
  return res.json();
}

export async function fetchTowerChatRecipients(): Promise<Array<{ username: string }>> {
  const res = await authFetch(`${API_BASE}/api/tower/chat/recipients`, { headers: authHeaders() });
  if (!res.ok) return [];
  return res.json();
}

export async function sendTowerChatMessage(opts: {
  text?: string;
  thread?: 'cmd' | 'eng';
  recipient_username?: string | null;
}): Promise<TowerChatMessage> {
  const form = new FormData();
  if (opts.text) form.append('text', opts.text);
  if (opts.thread) form.append('thread', opts.thread);
  if (opts.recipient_username) form.append('recipient_username', opts.recipient_username);
  const res = await authFetch(`${API_BASE}/api/tower/chat/messages`, {
    method: 'POST',
    headers: authHeaders(),
    body: form,
  });
  if (!res.ok) await towerAdminError(res, 'Не удалось отправить');
  return res.json();
}

export interface TowerOrder {
  id: number;
  created_at: string;
  faction_id: number;
  commander_username: string;
  target_username: string;
  target_name: string;
  target_lat: number;
  target_lon: number;
  note: string | null;
  dismissed: boolean;
}

export async function sendTowerOrder(body: {
  target_username: string;
  target_name: string;
  target_lat: number;
  target_lon: number;
  note?: string;
}): Promise<TowerOrder> {
  const res = await authFetch(`${API_BASE}/api/tower/orders`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  });
  if (!res.ok) await towerAdminError(res, 'Ошибка отправки приказа');
  return res.json();
}

export async function fetchTowerOrders(): Promise<TowerOrder[]> {
  const res = await authFetch(`${API_BASE}/api/tower/orders`, { headers: authHeaders() });
  if (!res.ok) return [];
  return res.json();
}

export async function fetchActiveTowerOrders(): Promise<TowerOrder[]> {
  const res = await authFetch(`${API_BASE}/api/tower/orders/active`, { headers: authHeaders() });
  if (!res.ok) return [];
  return res.json();
}

export async function dismissTowerOrder(orderId: number): Promise<TowerOrder | null> {
  const res = await authFetch(`${API_BASE}/api/tower/orders/${orderId}/dismiss`, {
    method: 'POST',
    headers: authHeaders(),
  });
  if (!res.ok) return null;
  const data = await res.json();
  return (data as { order?: TowerOrder }).order ?? null;
}

export async function pingTowerLocation(lat: number, lon: number, accuracy: number) {
  const res = await authFetch(`${API_BASE}/api/tower/location/ping`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ lat, lon, accuracy }),
  });
  if (!res.ok) throw new Error('Ошибка GPS');
  return res.json();
}

export interface TowerLocation {
  user_id: number;
  username: string;
  faction_id: number;
  lat: number;
  lon: number;
  accuracy: number;
  updated_at: string;
}

export async function fetchTowerRoster(): Promise<TowerLocation[]> {
  const res = await authFetch(`${API_BASE}/api/tower/location/roster`, { headers: authHeaders() });
  if (!res.ok) return [];
  return res.json();
}
