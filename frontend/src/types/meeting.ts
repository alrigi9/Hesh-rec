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
  audio_filename?: string;
  file_size?: string;
  file_size_bytes?: number;
  [key: string]: any;
}

export interface MeetingSession {
  id?: string;
  title: string;
  meeting_date?: string;
  date?: string;
  duration_minutes?: number;
  duration?: string;
  template?: string;
  participants?: string[];
  tags?: string[];
  tldr?: string;
  executive_summary?: string;
  summary?: string;
  sections?: MeetingSection[];
  discussion_pillars?: MeetingSection[];
  action_items?: ActionItem[];
  open_questions?: (string | { question: string; raised_by?: string })[];
  ai_suggestions?:
    | { items?: AISuggestionItem[]; unresolved?: string[]; gaps?: string[]; recommendations?: string[] }
    | AISuggestionItem[]
    | string[];
  strategic_insights?:
    | { items?: AISuggestionItem[]; unresolved?: string[]; gaps?: string[]; recommendations?: string[] }
    | AISuggestionItem[]
    | string[];
  mindmap_markdown?: string;
  mindmap?: any;
  transcript?: string | TranscriptSegment[];
  transcript_segments?: TranscriptSegment[];
  full_transcript_text?: string;
  metadata?: MeetingMetadata;
  raw_markdown?: string;
  user_id?: string;
  created_at?: string;
  [key: string]: any;
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
