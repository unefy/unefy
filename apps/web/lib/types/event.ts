export type EventType =
  | "training"
  | "meeting"
  | "celebration"
  | "competition"
  | "other"

export type EventStatus = "scheduled" | "cancelled"

export interface ClubEvent {
  id: string
  title: string
  description: string | null
  event_type: EventType
  location: string | null
  starts_at: string
  ends_at: string | null
  all_day: boolean
  registration_required: boolean
  registration_deadline: string | null
  max_participants: number | null
  status: EventStatus
  registered_count: number
  created_at: string
  updated_at: string
}

export interface EventRegistration {
  id: string
  event_id: string
  member_id: string
  member_name: string | null
  status: "registered" | "waitlist"
  note: string | null
  created_at: string
}

export interface ClubEventDetail extends ClubEvent {
  registrations: EventRegistration[]
}

export interface EventCreate {
  title: string
  description?: string | null
  event_type?: EventType
  location?: string | null
  starts_at: string
  ends_at?: string | null
  all_day?: boolean
  registration_required?: boolean
  registration_deadline?: string | null
  max_participants?: number | null
}

export interface EventUpdate extends Partial<EventCreate> {
  status?: EventStatus
}

export interface EventListResponse {
  data: ClubEvent[]
  meta: {
    total: number
    page: number
    per_page: number
    total_pages: number
  }
}
