export type ProjectStage =
  | "BRIEF"
  | "SCRIPT"
  | "STORYBOARD_APPROVED"
  | "VIDEOS"
  | "NARRATION"
  | "RENDERING"
  | "ASSEMBLED"
  | "FAILED";

export type ShotStatus =
  | "PENDING"
  | "SUBMITTED"
  | "GENERATING"
  | "DOWNLOADING"
  | "VALIDATING"
  | "DONE"
  | "FAILED";

export type JobStatus = "QUEUED" | "RUNNING" | "DONE" | "FAILED";

export type JobType =
  | "PLAN_SCRIPT"
  | "GENERATE_VIDEO"
  | "GENERATE_TTS"
  | "ASSEMBLE";

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
  provider_job_id: string | null;
  provider_status: string | null;
  status: ShotStatus;
  error_message: string | null;
  retry_count: number;
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
