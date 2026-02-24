// Mirror backend Pydantic models

export type WSMessageType =
  | 'transcript'
  | 'keyword_suggestions'
  | 'encounter_state'
  | 'soap_note'
  | 'session_reset'
  | 'status'
  | 'error';

export interface WSMessage {
  type: WSMessageType;
  data: Record<string, unknown>;
}

// Encounter state
export interface Symptom {
  name: string;
  duration?: string | null;
  severity?: string | null;
  character?: string | null;
  location?: string | null;
  onset?: string | null;
  radiation?: string | null;
  time_course?: string | null;
  aggravating: string[];
  relieving: string[];
  associated: string[];
}

export interface SymptomFocus {
  canonical_name: string;
  aliases: string[];
  first_seen_turn: number;
  priority?: string | null;
}

export interface SymptomKnownInfo {
  duration?: string | null;
  onset?: string | null;
  location?: string | null;
  character?: string | null;
  radiation?: string | null;
  severity?: string | null;
  time_course?: string | null;
  associated: string[];
  aggravating: string[];
  relieving: string[];
  negatives: string[];
  red_flags: string[];
  notes: string[];
  last_updated_turn: number;
}

export interface SymptomKeywordState {
  symptom: string;
  addressed_keywords: string[];
  new_keywords: string[];
  active_keywords: string[];
  rationale?: string | null;
  priority: QuestionPriority;
}

export interface Medication {
  name: string;
  dose?: string | null;
  frequency?: string | null;
}

export interface VitalSign {
  name: string;
  value: string;
}

export interface DemographicsData {
  name?: string | null;
  age?: string | null;
  sex?: string | null;
  other: string[];
}

export interface ChiefComplaintStructured {
  primary?: string | null;
  duration?: string | null;
  onset?: string | null;
  site?: string | null;
  character?: string | null;
  radiation?: string | null;
  severity?: string | null;
  time_course?: string | null;
  characteristics: string[];
  associated: string[];
  aggravating: string[];
  relieving: string[];
}

export interface EncounterStateData {
  demographics: DemographicsData;
  chief_complaint?: string | null;
  chief_complaint_structured: ChiefComplaintStructured;
  symptoms: Symptom[];
  history_of_present_illness?: string | null;
  past_medical_history: string[];
  medications: Medication[];
  allergies: string[];
  family_history: string[];
  social_history: string[];
  review_of_systems: Record<string, string[]>;
  vitals: VitalSign[];
  physical_exam_findings: string[];
  domains_covered: string[];
  red_flags: string[];
  isolated_symptoms: SymptomFocus[];
  symptom_known_info: Record<string, SymptomKnownInfo>;
  symptom_keyword_state: Record<string, SymptomKeywordState>;
}

// Questions
export type QuestionPriority = 'critical' | 'high' | 'medium' | 'low';

export interface KeywordSuggestionGroup {
  category: string;
  priority: QuestionPriority;
  keywords: string[];
  rationale?: string | null;
}

// SOAP Note
export interface SOAPNote {
  subjective: string;
  objective: string;
  assessment: string;
  plan: string;
}

export interface SessionResetPayload {
  transcript: string;
  keyword_suggestions?: KeywordSuggestionGroup[];
  encounter_state: EncounterStateData;
  soap_note: SOAPNote | null;
  pipeline_latency_ms: number | null;
  message: string;
}

// Connection status
export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error';
