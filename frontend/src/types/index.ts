export type ProjectStage =
  | "BRIEF"
  | "SCRIPT"
  | "STORYBOARD_APPROVED"
  | "VIDEOS"
  | "NARRATION"
  | "ASSEMBLED"
  | "FAILED";

export type ShotStatus = "PENDING" | "GENERATING" | "DONE" | "FAILED";

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
  description: string;
  visual_prompt: string;
  narration_text: string | null;
  image_url: string | null;
  video_path: string | null;
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

export interface ProjectDetail {
  id: string;
  product_name: string;
  brief: string;
  audience: string;
  tone: string;
  cta: string;
  script: string | null;
  stage: ProjectStage;
  product_image_path: string | null;
  logo_path: string | null;
  music_path: string | null;
  narration_path: string | null;
  final_video_path: string | null;
  created_at: string;
  updated_at: string;
  shots: ShotResponse[];
  jobs: JobResponse[];
}

export interface ProjectSummary {
  id: string;
  product_name: string;
  stage: ProjectStage;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreate {
  product_name: string;
  brief: string;
  audience: string;
  tone: string;
  cta: string;
}
