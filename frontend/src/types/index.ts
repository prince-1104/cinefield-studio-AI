export type ProjectStage =
  | "BRIEF"
  | "SCRIPT"
  | "STORYBOARD_APPROVED"
  | "VIDEOS"
  | "NARRATION"
  | "RENDERING"
  | "ASSEMBLED"
  | "FAILED"
  | "ASSEMBLY_QUEUED"
  | "ASSEMBLING"
  | "ASSEMBLY_FAILED";

export type ShotStatus =
  | "QUEUED"
  | "PENDING"
  | "CLAIMED"
  | "SUBMITTED"
  | "GENERATING"
  | "DOWNLOADING"
  | "VALIDATING"
  | "COMPLETED"
  | "DONE"
  | "FAILED"
  | "RETRYING"
  | "CANCELLED";

export type JobStatus = "QUEUED" | "RUNNING" | "DONE" | "FAILED";

export type JobType =
  | "PLAN_SCRIPT"
  | "GENERATE_VIDEO"
  | "GENERATE_TTS"
  | "ASSEMBLE";

export interface VideoModelInfo {
  id: string;
  name: string;
  provider: string;
  provider_name: string;
  description: string;
  supported_aspect_ratios: string[];
  supported_durations: number[];
  default_duration: number;
  is_default: boolean;
  requires_resource_id?: boolean;
  capabilities?: string[];
  is_available?: boolean;
  unavailability_reason?: string | null;
}

export interface ModelParameter {
  name: string;
  type: "string" | "integer" | "float" | "boolean" | "list";
  description: string;
  default?: any;
  options?: any[] | null;
  min_value?: number | null;
  max_value?: number | null;
  required: boolean;
}

export interface ModelSpec {
  id: string;
  provider: string;
  name: string;
  capabilities: string[];
  description: string;
  is_available: boolean;
  unavailability_reason?: string | null;
  supported_durations?: number[];
  supported_aspect_ratios?: string[];
  supported_parameters: ModelParameter[];
  default_duration?: number;
  input_price_per_million?: number;
  output_price_per_million?: number;
  video_price_per_second?: number;
}

export interface ShotResponse {
  id: string;
  project_id: string;
  shot_number: number;
  start_time: number;
  end_time: number;
  target_duration: number;
  actual_duration: number | null;
  description: string;
  visual_prompt: string;
  camera_motion: string | null;
  transition: string | null;
  narration_text: string | null;
  image_url: string | null;
  video_path: string | null;
  provider?: string | null;
  model?: string | null;
  provider_job_id: string | null;
  provider_status: string | null;
  status: ShotStatus;
  error_message: string | null;
  retry_count: number;
  started_at?: string | null;
  completed_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface JobResponse {
  id: string;
  project_id: string;
  job_type: JobType;
  status: JobStatus;
  payload: Record<string, any> | null;
  result: Record<string, any> | null;
  error_message: string | null;
  attempt: number;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface VideoMetadata {
  duration: number;
  width: number;
  height: number;
  fps: number;
  vcodec: string;
  acodec: string;
  size_bytes: number;
}

export interface ProjectDetail {
  id: string;
  product_name: string;
  brief: string;
  audience: string;
  tone: string;
  cta: string;

  target_duration: number;
  shot_count: number;
  aspect_ratio: string;
  selected_video_model?: string | null;
  selected_video_provider?: string | null;
  progress_percent: number;
  current_stage_label?: string | null;

  script: string | null;
  stage: ProjectStage;
  product_image_path: string | null;
  logo_path: string | null;
  music_path: string | null;
  narration_path: string | null;
  final_video_path: string | null;
  video_metadata?: VideoMetadata | null;

  created_at: string;
  updated_at: string;
  shots: ShotResponse[];
  jobs: JobResponse[];
}

export interface ProjectSummary {
  id: string;
  product_name: string;
  stage: ProjectStage;
  target_duration: number;
  shot_count: number;
  selected_video_model?: string | null;
  selected_video_provider?: string | null;
  progress_percent: number;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreate {
  product_name: string;
  brief: string;
  audience: string;
  tone: string;
  cta: string;
  target_duration?: number;
  shot_count?: number;
  aspect_ratio?: string;
  selected_video_model?: string;
  selected_video_provider?: string;
}

export interface TimelineSettings {
  duration_target_seconds: number;
  aspect_ratio: "16:9" | "9:16";
  fps: number;
  width: number;
  height: number;
}

export interface TimelineClip {
  id: string;
  shot_id?: string | null;
  shot_number: number;
  source_path: string;
  source_duration: number;
  source_start: number;
  source_end: number;
  timeline_start: number;
  duration: number;
  volume: number;
  transition: string;
  description?: string | null;
  visual_prompt?: string | null;
}

export interface TimelineOverlay {
  id: string;
  asset_type: "logo" | "watermark" | "badge";
  asset_path: string;
  timeline_start: number;
  timeline_end: number;
  position: "top_right" | "top_left" | "bottom_right" | "bottom_left" | "center";
  scale: number;
  opacity: number;
}

export interface TimelineAudio {
  id: string;
  track_type: "narration" | "music";
  source_path: string;
  timeline_start: number;
  duration: number;
  volume: number;
  fade_in?: number;
  fade_out?: number;
  ducking?: boolean;
}

export interface TimelineCaption {
  id: string;
  text: string;
  timeline_start: number;
  timeline_end: number;
  font_size: number;
  font_color: string;
  position: "bottom" | "center" | "top";
  style: "standard" | "boxed" | "glow";
}

export interface TimelineData {
  settings: TimelineSettings;
  video_clips: TimelineClip[];
  overlays: TimelineOverlay[];
  audio_tracks: TimelineAudio[];
  captions: TimelineCaption[];
}

export interface TimelineEditResponse {
  id: string;
  project_id: string;
  version: number;
  timeline_data: TimelineData;
  is_current: boolean;
  rendered_video_path?: string | null;
  render_job_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface TimelineEditSummary {
  id: string;
  version: number;
  is_current: boolean;
  clip_count: number;
  duration: number;
  has_rendered_video: boolean;
  created_at: string;
}

export interface WebsiteAssetCandidate {
  url: string;
  asset_type: "logo" | "product" | "screenshot" | "favicon";
  title?: string | null;
  width?: number | null;
  height?: number | null;
}

export interface WebsiteAnalysisResult {
  url: string;
  domain: string;
  title: string;
  description: string;
  headings: string[];
  key_content: string;
  brand_colors: string[];
  logo_candidates: WebsiteAssetCandidate[];
  product_image_candidates: WebsiteAssetCandidate[];
}

export interface CreativeBriefRequest {
  prompt: string;
  website_url?: string | null;
  website_data?: WebsiteAnalysisResult | null;
  video_category: string;
  target_duration?: number;
  aspect_ratio?: string;
  creative_style?: string | null;
  target_audience?: string | null;
  language?: string;
  narration_preference?: string;
  cta?: string | null;
}

export interface GeneratedBriefResponse {
  product_name: string;
  brief: string;
  tone: string;
  audience: string;
  cta: string;
  target_duration: number;
  shot_count: number;
  aspect_ratio: string;
  video_category: string;
  suggested_music_mood: string;
  creative_reasoning: string;
  hook?: string | null;
  narration_preview?: string | null;
  provider_used: string;
}

export interface ImportAssetResponse {
  asset_path: string;
  url: string;
  file_name: string;
  size: number;
  content_type: string;
}

export interface GenerationProgressEvent {
  event_type: string;
  project_id: string;
  shot_id?: string | null;
  shot_number?: number | null;
  job_id?: string | null;
  provider?: string | null;
  model?: string | null;
  status: string;
  previous_status?: string | null;
  error?: string | null;
  video_path?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  progress?: Record<string, any>;
  timestamp: string;
}

export interface OverviewMetrics {
  total_spend: number;
  actual_spend: number;
  estimated_spend: number;
  unknown_spend: number;
  total_requests: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  total_video_generations: number;
  successful_generations: number;
  failed_generations: number;
  total_video_seconds: number;
  total_projects_using_ai: number;
}

export interface ProviderMetric {
  provider: string;
  request_count: number;
  total_cost: number;
  input_tokens: number;
  output_tokens: number;
  video_generation_count: number;
  failure_rate: number;
}

export interface ModelMetric {
  provider: string;
  model: string;
  total_requests: number;
  actual_cost: number;
  estimated_cost: number;
  total_cost: number;
  avg_cost_per_request: number;
  input_tokens: number;
  output_tokens: number;
  video_generation_count: number;
  failure_rate: number;
}

export interface ProjectCostMetric {
  project_id: string;
  project_name: string;
  owner: string;
  total_requests: number;
  claude_model: string;
  claude_input_tokens: number;
  claude_output_tokens: number;
  seedance_model: string;
  video_generation_count: number;
  successful_videos: number;
  failed_videos: number;
  actual_spend: number;
  estimated_spend: number;
  total_spend: number;
}

export interface ProjectDetailMetrics {
  project_id: string;
  project_name: string;
  total_spend: number;
  claude_spend: number;
  seedance_spend: number;
  retry_spend: number;
  failed_spend: number;
  cost_per_video: number;
  cost_per_shot: number;
  claude_tokens: { input: number; output: number; total: number };
  video_generations_count: number;
  shot_costs: Record<string, number>;
  records_count: number;
}

export interface AIUsageRecord {
  id: string;
  project_id?: string | null;
  shot_id?: string | null;
  job_id?: string | null;
  provider: string;
  model: string;
  operation: string;
  provider_request_id?: string | null;
  provider_task_id?: string | null;
  input_tokens?: number | null;
  output_tokens?: number | null;
  cached_input_tokens?: number | null;
  video_duration_seconds?: number | null;
  billing_unit: string;
  unit_quantity: number;
  unit_price: number;
  estimated_cost: number;
  actual_cost?: number | null;
  currency: string;
  cost_status: string;
  usage_origin?: string;
  request_status: string;
  error_code?: string | null;
  created_at: string;
  completed_at?: string | null;
}

export interface PaginatedUsage {
  items: AIUsageRecord[];
  total: number;
  limit: number;
  offset: number;
}


