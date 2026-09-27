import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type {
  AddRoleBody,
  DemoUser,
  GeocodeMatch,
  HazardRegion,
  HazardReport,
  HelpRequest,
  LatLon,
  LiveLocation,
  NearbyVolunteer,
  MeResponse,
  Message,
  OnboardingBody,
  ProfileUpdate,
  RankedResponse,
  RequestCreateBody,
  SimState,
  Role,
  Triage,
  TractsResponse,
} from '../lib/types'
import { api, post, postForBlob } from './client'

// Polling intervals from PLAN.md §0.1 (WebSocket realtime comes later).
const POLL_REQUESTER_MS = 5_000
const POLL_RANKED_MS = 10_000
// Hazards change slowly and the backend caches them for 5 minutes (PLAN.md §7).
const POLL_HAZARDS_MS = 5 * 60_000

export const keys = {
  me: ['me'] as const,
  mine: ['requests', 'mine'] as const,
  ranked: ['requests', 'ranked'] as const,
  request: (id: string) => ['requests', id] as const,
}

export function useMe() {
  return useQuery({
    queryKey: keys.me,
    queryFn: () => api<MeResponse>('/api/me', { allow401: true }),
    retry: false,
    staleTime: 60_000,
  })
}

export function useDemoUsers(enabled: boolean) {
  return useQuery({
    queryKey: ['demo-users'],
    queryFn: () => api<{ users: DemoUser[] }>('/api/auth/demo-users'),
    enabled,
  })
}

/** After any login, cache the new user so guards route correctly. */
export function useLogin() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (args: { kind: 'google'; credential: string } | { kind: 'demo'; userId: string }) =>
      args.kind === 'google'
        ? post<MeResponse>('/api/auth/google', { credential: args.credential })
        : post<MeResponse>('/api/auth/demo', { user_id: args.userId }),
    onSuccess: (data) => {
      qc.clear()
      qc.setQueryData(keys.me, data)
    },
  })
}

export function useLogout() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => post('/api/auth/logout'),
    onSettled: () => {
      qc.clear()
      window.location.assign('/login')
    },
  })
}

export function useOnboarding() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: OnboardingBody) => post<MeResponse>('/api/onboarding', body),
    onSuccess: (data) => qc.setQueryData(keys.me, data),
  })
}

export function useUpdateProfile() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: ProfileUpdate) => api<MeResponse>('/api/me', { method: 'PATCH', json: body }),
    onSuccess: (data) => {
      qc.setQueryData(keys.me, data)
      // The profile is re-embedded in the background; Muse Spark takes ~5-20 s. Refresh the ranking as it lands
      // (the ranked list also polls every 10 s on the volunteer page).
      if (data.rematching) {
        for (const delay of [10_000, 25_000]) setTimeout(() => qc.invalidateQueries({ queryKey: keys.ranked }), delay)
      }
    },
  })
}

/** Adds the second profile (volunteer or requester) to the signed-in account. */
export function useAddRole() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: AddRoleBody) => post<MeResponse>('/api/me/roles', body),
    onSuccess: (data) => {
      qc.setQueryData(keys.me, data)
      if (data.rematching) {
        for (const delay of [10_000, 25_000]) setTimeout(() => qc.invalidateQueries({ queryKey: keys.ranked }), delay)
      }
    },
  })
}

/** Switches the active mode (home page); the lists differ per mode, so drop their caches. */
export function useSwitchMode() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (role: Role) => api<MeResponse>('/api/me', { method: 'PATCH', json: { role } }),
    onSuccess: (data) => {
      qc.setQueryData(keys.me, data)
      qc.invalidateQueries({ queryKey: keys.mine })
      qc.invalidateQueries({ queryKey: keys.ranked })
    },
  })
}

export function useMyRequests(pollMs = POLL_REQUESTER_MS) {
  return useQuery({
    queryKey: keys.mine,
    queryFn: () => api<{ requests: HelpRequest[] }>('/api/requests/mine'),
    refetchInterval: pollMs,
  })
}

export function useRanked() {
  return useQuery({
    queryKey: keys.ranked,
    queryFn: () => api<RankedResponse>('/api/requests/ranked'),
    refetchInterval: POLL_RANKED_MS,
  })
}

export function useRequest(id: string) {
  return useQuery({
    queryKey: keys.request(id),
    queryFn: () => api<{ request: HelpRequest }>(`/api/requests/${id}`),
    refetchInterval: POLL_REQUESTER_MS,
  })
}

export function useCheckEmergency() {
  return useMutation({ mutationFn: (text: string) => post<{ emergency: boolean }>('/api/requests/check', { text }) })
}

/** The triage card for a draft request. Saves nothing; can take several seconds while the AI reads it. */
export function usePreviewRequest() {
  return useMutation({
    mutationFn: (body: RequestCreateBody) => post<{ triage: Triage; emergency: boolean }>('/api/requests/preview', body),
  })
}

export function useCreateRequest() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: RequestCreateBody) => post<{ request: HelpRequest; show_911: boolean }>('/api/requests', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.mine }),
  })
}

export type RequestAction = 'claim' | 'release' | 'resolve' | 'cancel'

export function useRequestAction() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, action }: { id: string; action: RequestAction }) =>
      post<{ request: HelpRequest }>(`/api/requests/${id}/${action}`),
    onSuccess: ({ request }) => qc.setQueryData(keys.request(request.id), { request }),
    onSettled: () => qc.invalidateQueries({ queryKey: ['requests'] }),
  })
}

export function listMessages(requestId: string, after?: string) {
  const qs = after ? `?after=${encodeURIComponent(after)}` : ''
  return api<{ messages: Message[] }>(`/api/requests/${requestId}/messages${qs}`)
}

export function sendMessage(requestId: string, text: string) {
  return post<{ message: Message }>(`/api/requests/${requestId}/messages`, { text })
}

/** Which voice features the server has keys for. Buttons for the others stay hidden. */
export function useVoiceStatus() {
  return useQuery({
    queryKey: ['voice', 'status'],
    queryFn: () => api<{ transcribe: boolean; speak: boolean }>('/api/voice/status'),
    staleTime: 5 * 60_000,
    retry: false,
  })
}

export function transcribeAudio(wav: Blob) {
  const form = new FormData()
  form.append('audio', wav, 'recording.wav')
  return api<{ text: string }>('/api/voice/transcribe', { method: 'POST', body: form })
}

export function speakText(text: string, language = 'en') {
  return postForBlob('/api/voice/speak', { text, language })
}

/** Street-address search (US Census geocoder via the backend). It does not match place names. */
export function searchAddress(q: string) {
  return api<{ matches: GeocodeMatch[] }>(`/api/geocode?q=${encodeURIComponent(q)}`)
}

/** Approximate areas of volunteers around a point, for the requester's map. */
export function useNearbyVolunteers(center: LatLon | null) {
  return useQuery({
    queryKey: ['volunteers', 'nearby', center?.lat, center?.lon] as const,
    queryFn: () => api<{ volunteers: NearbyVolunteer[]; radius_km: number }>(`/api/volunteers/nearby?lat=${center?.lat}&lon=${center?.lon}`),
    enabled: center !== null,
    staleTime: 60_000,
  })
}

/** Live location sharing on a claimed request (polling; the backend only ever returns the other person's point). */
export function postLocation(requestId: string, body: LatLon & { accuracy?: number }) {
  return post<{ ok: boolean; throttled: boolean }>(`/api/requests/${requestId}/location`, body)
}

export function stopSharingLocation(requestId: string) {
  return api<{ ok: boolean }>(`/api/requests/${requestId}/location`, { method: 'DELETE' })
}

const POLL_LOCATION_MS = 5_000

export function useOtherLocation(requestId: string, enabled: boolean) {
  return useQuery({
    queryKey: ['requests', requestId, 'location'] as const,
    queryFn: () => api<{ other: LiveLocation | null; simulated: boolean; stale_after_s: number }>(`/api/requests/${requestId}/location`),
    enabled,
    refetchInterval: POLL_LOCATION_MS,
    retry: false,
  })
}

/** Hazard report for a point. Coordinates are rounded to ~1 km, the same key the backend caches on. */
export function useHazards(point: LatLon | null | undefined) {
  const lat = point ? Math.round(point.lat * 100) / 100 : null
  const lon = point ? Math.round(point.lon * 100) / 100 : null
  return useQuery({
    queryKey: ['hazards', lat, lon],
    queryFn: () => api<HazardReport>(`/api/hazards?lat=${lat}&lon=${lon}`),
    enabled: lat !== null && lon !== null,
    staleTime: POLL_HAZARDS_MS,
    refetchInterval: POLL_HAZARDS_MS,
  })
}

/** Georgia's active NWS alert areas for the volunteer map. */
export function useHazardRegion(enabled: boolean) {
  return useQuery({
    queryKey: ['hazards', 'region'],
    queryFn: () => api<HazardRegion>('/api/hazards/region'),
    enabled,
    staleTime: POLL_HAZARDS_MS,
    refetchInterval: POLL_HAZARDS_MS,
  })
}

export type Bbox = [number, number, number, number] // minLon, minLat, maxLon, maxLat

/** EJI band shading for the visible map area. The box is snapped outward to 0.05° so small pans reuse the cache. */
export function useTracts(bbox: Bbox | null, zoom: number, enabled: boolean) {
  const snap = (v: number, up: boolean) => (up ? Math.ceil(v * 20) : Math.floor(v * 20)) / 20
  const box = bbox ? [snap(bbox[0], false), snap(bbox[1], false), snap(bbox[2], true), snap(bbox[3], true)] : null
  return useQuery({
    queryKey: ['tracts', box?.join(','), zoom],
    queryFn: () => api<TractsResponse>(`/api/tracts?bbox=${box!.join(',')}&zoom=${zoom}`),
    enabled: enabled && box !== null,
    staleTime: 60 * 60_000, // EJI doesn't change during a session
    placeholderData: keepPreviousData, // keep the old shading on screen while a pan loads
  })
}

/** Demo scenario state. The endpoint is a 404 outside demo mode, so an error just means "no switch". */
export function useSim() {
  return useQuery({
    queryKey: ['sim'],
    queryFn: () => api<SimState>('/api/sim'),
    retry: false,
    staleTime: 30_000,
    refetchInterval: 30_000, // pick up a scenario someone else switched on
  })
}

/** Turn a demo scenario on or off. Hazards, rankings and requests all change, so refetch them. */
export function useSetSim() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (scenarioId: string | null) =>
      scenarioId ? post<SimState>('/api/sim/activate', { scenario_id: scenarioId }) : post<SimState>('/api/sim/deactivate'),
    onSuccess: (state) => {
      qc.setQueryData(['sim'], state)
      for (const key of [['hazards'], ['requests'], ['sim']]) qc.invalidateQueries({ queryKey: key })
    },
  })
}
