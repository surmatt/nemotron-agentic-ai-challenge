export type StepName = "extract" | "correct" | "match" | "compare" | "document";
export type StepStatus = "idle" | "queued" | "running" | "done" | "failed";
export const STEPS: StepName[] = ["extract", "correct", "match", "compare", "document"];

export interface DocumentView {
  tex: string;
  tex_sha256: string;
  tex_url: string;
  pdf_url: string | null;
  pdf_bytes: number | null;
  file: string;
}

export interface SiteStatus {
  running: boolean;
  started_at: string | null;
  error: string | null;
  built: boolean;
  url: string;
  summary: {
    finished_at: string;
    scan_pages: number;
    entry_pages: number;
    agent_runs: number;
    latex: { engine: string | null; compiled: number; failed: { file: string; error: string }[]; note?: string };
  } | null;
}

export type BBox = [number, number, number, number];
export type Summary = Record<string, unknown>;

export interface StepState {
  status: StepStatus;
  started_at?: string;
  finished_at?: string;
  elapsed_seconds?: number;
  error?: string | null;
  progress?: { done: number; total: number; label: string };
  summary?: Summary;
  models: string[];
  needs?: StepName[];
  blocked_by?: StepName | null;
  note?: string;
  archived_previous?: string | null;
  seeded_from?: { kind: string; path: string; saved_at?: string | null };
}

export interface DiffOp {
  op: "equal" | "insert" | "delete";
  text: string;
}

export interface Block {
  index: number;
  cls: string;
  bbox: BBox;
  parse_text: string;
  text: string;
  text_source?: string | null;
  review_flag?: string | null;
  super_vl_text?: string | null;
  long_s_rule_changed?: boolean | null;
  eligible_for_correction: boolean;
  diff?: DiffOp[];
  correction?: {
    model?: string;
    elapsed_seconds?: number;
    finish_reason?: string;
    started_at?: string;
    completion_tokens?: number;
  };
}

export interface Furniture {
  index: number;
  cls: string;
  bbox: BBox;
  text: string;
}

export interface PageView {
  page_id: string;
  status: string;
  running_header: string;
  header_kind: string;
  header_title: string | null;
  page_numbers: string[];
  finish_reason: string;
  body_chars: number;
  block_classes: string[];
  furniture: Furniture[];
  blocks: Block[];
}

export interface Candidate {
  page_id: string;
  revision_id: string;
  title: string;
  url: string;
  best_rank: number;
  bm25: Record<string, { rank: number; score: number }>;
  title_similarity: number;
  context_overlap: number;
  cosine?: number;
  rerank_logit?: number;
  rerank_position?: number;
  excerpt: string;
}

export interface Decision {
  status: "accepted" | "rejected" | "error";
  method?: string;
  reason?: string;
  error?: string;
  error_type?: string;
  page_id?: string;
  title?: string;
  rerank_logit?: number;
  cosine?: number;
  margin_to_next?: number | null;
  title_similarity?: number;
  context_overlap?: number;
  bm25_best_rank?: number;
  thresholds?: Record<string, number>;
}

export interface ArticleView {
  page_id: string;
  revision_id: string;
  title: string;
  url: string;
  revision_url: string;
  chars: number;
  text_sha256: string;
  dataset_revision: string;
  excerpt: string;
}

export interface SearchHit {
  page_id: string;
  title: string;
  url?: string | null;
  rank: number;
  bm25: number;
  removed: string | null;
  status: "candidate" | "removed" | "not_scored";
}

export interface WikiSearch {
  id: string;
  query: string;
  kind: string;
  top_k?: number;
  excerpt_chars?: number;
  hits: SearchHit[];
}

export interface ModelQuery {
  chars: number;
  documents: number;
  text: string | null;
  document_format: string;
  note: string | null;
}

export interface SearchTerms {
  frequency: string[];
  dictionary_filter: boolean;
  llm: {
    status: "ok" | "failed" | "skipped";
    title?: string | null;
    terms?: string[];
    model?: string;
    cached?: boolean;
    reason?: string;
    error?: string;
    error_type?: string;
    raw_path?: string;
  };
}

export interface MatchView {
  mode: "model" | "lexical";
  searches: WikiSearch[];
  search_terms?: SearchTerms;
  searches_complete: boolean;
  model_query: ModelQuery | null;
  queries?: string[];
  headword_variant?: string | null;
  candidate_count?: number;
  query_chars?: number;
  decision: Decision;
  candidates: Candidate[];
  article?: ArticleView | null;
  list_pages_removed_after_fetch?: { page_id: string; title: string }[];
}

export interface Snippet {
  offset: number;
  text: string;
}

export interface TermRow {
  term: string;
  z: number;
  count_britannica: number;
  count_wikipedia: number;
  britannica_snippet?: Snippet | null;
  wikipedia_snippet?: Snippet | null;
}

export interface Pair {
  entry_id: string;
  headword: string | null;
  match_method: string;
  article: { page_id: string; revision_id: string; title: string; url: string; revision_url: string };
  britannica: {
    tokens_raw: number;
    tokens_kept: number;
    types: number;
    unverified_tokens: number;
    unverified_rate: number | null;
    unverified_examples: string[];
  };
  wikipedia: { tokens: number; types: number };
  length_ratio_wiki_to_britannica: number | null;
  top_terms_jaccard: number;
  frequency_cosine: number;
  shared_terms: { term: string; count_britannica: number; count_wikipedia: number }[];
  distinctive_britannica: TermRow[];
  distinctive_wikipedia: TermRow[];
}

export interface Entry {
  entry_id: string;
  headword: string | null;
  start_kind: "headword" | "continuation";
  headword_source: string;
  continued: boolean;
  chars: number;
  text: string;
  text_sha256: string;
  pages: { page_id: string; filename: string; row_index: number }[];
  block_indexes: number[];
  skip_reason: string | null;
  match: MatchView | null;
  pair: Pair | null;
}

export interface Failure {
  stage: string;
  error_type?: string;
  error: string;
  at: string;
  block_index?: number;
  entry_id?: string;
  page_id?: string;
}

export interface WorkspaceView {
  id: string;
  kind: "upload" | "corpus";
  title: string;
  meta: Record<string, any>;
  scan: { image_url: string; width?: number; height?: number; sha256: string; filename: string };
  steps: Record<StepName, StepState>;
  running: boolean;
  page: PageView | null;
  entries: Entry[];
  document: DocumentView | null;
  entry_text: "extract" | "correct" | null;
  failures: Failure[];
  history: string[];
  crop_url: string;
  raw_url: string;
}

export interface UploadRow {
  id: string;
  filename: string;
  uploaded_at: string;
  source: { kind: string; row_index?: number; page_id?: string };
  steps: Record<StepName, StepStatus>;
}

export interface CorpusRow {
  row_index: number;
  page_id: string;
  filename: string;
  volume_id: string;
  status: string;
  running_header: string | null;
  entries: number;
  accepted: number;
}

export interface CorpusIndex {
  dataset: string;
  revision: string;
  license: { spdx: string; attribution: string };
  entry_text: string;
  summaries: Record<string, Summary | null>;
  pages: CorpusRow[];
  has_artifacts: boolean;
}

export interface ServiceRow {
  configured: boolean;
  status: "ok" | "failed" | "missing" | "not_tested";
  detail?: string;
}

export interface ServicesReport {
  checked_at: string | null;
  services: Record<"parse" | "super" | "retrieval" | "wikipedia", ServiceRow>;
}
