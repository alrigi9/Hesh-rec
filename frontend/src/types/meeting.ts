export interface ActionItem {
  id?: string;
  number?: number;
  task?: string;
  description?: string;
  owner?: string;
  assignee?: string;
  due_date?: string;
  due_text?: string;
  priority?: "HIGH" | "MED" | "LOW" | string;
  status?: "pending" | "completed" | string;
  notes?: string;
}

export interface MeetingSection {
  n?: number;
  title: string;
  narrative: string;
  decisions?: string[];
  action_items?: ActionItem[];
}

export interface TranscriptSegment {
  timestamp?: string;
  speaker?: string;
  text: string;
  start?: number;
  seconds?: number;
  end?: number;
}

export interface AISuggestionItem {
  label?: string;
  title?: string;
  detail?: string;
  body?: string;
}

export interface MeetingMetadata {
  session_id?: string;
  user_id?: string;
  template_type?: string;
  source_file?: string;
  duration?: string;
  duration_seconds?: number;
  processed_at?: string;
  model?: string;
  audio_url?: string;
  file_size?: string;
}

export interface MeetingSession {
  id?: string;
  title: string;
  meeting_date?: string;
  duration_minutes?: number;
  participants?: string[];
  tags?: string[];
  tldr?: string;
  sections?: MeetingSection[];
  action_items?: ActionItem[];
  open_questions?: (string | { question: string; raised_by?: string })[];
  ai_suggestions?:
    | { items?: AISuggestionItem[] }
    | AISuggestionItem[]
    | string[];
  transcript_segments?: TranscriptSegment[];
  full_transcript_text?: string;
  metadata?: MeetingMetadata;
  raw_markdown?: string;
}

export interface SessionListItem {
  id: string;
  raw_id?: string;
  title: string;
  duration: string;
  date_display: string;
  action_count: number;
  decision_count: number;
  tags: string[];
  template_type?: string;
  data: MeetingSession;
}
