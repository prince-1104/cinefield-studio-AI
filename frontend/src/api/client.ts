import axios from "axios";
import {
  JobResponse,
  ProjectCreate,
  ProjectDetail,
  ProjectSummary,
  ShotResponse,
  TimelineData,
  TimelineEditResponse,
  TimelineEditSummary,
  VideoModelInfo,
  WebsiteAnalysisResult,
  CreativeBriefRequest,
  GeneratedBriefResponse,
  ImportAssetResponse,
} from "../types";

const api = axios.create({
  baseURL: "/api",
});

export async function getVideoModels(): Promise<VideoModelInfo[]> {
  const res = await api.get<VideoModelInfo[]>("/video-models");
  return res.data;
}

export async function selectProjectModel(
  projectId: string,
  model: string,
  provider?: string
): Promise<ProjectDetail> {
  const res = await api.put<ProjectDetail>(`/projects/${projectId}/model`, {
    model,
    provider: provider || null,
  });
  return res.data;
}

export async function updateShotPrompt(
  projectId: string,
  shotId: string,
  visualPrompt: string
): Promise<ShotResponse> {
  const res = await api.put<ShotResponse>(`/projects/${projectId}/shots/${shotId}/prompt`, {
    visual_prompt: visualPrompt,
  });
  return res.data;
}

export async function generateShotVideo(
  projectId: string,
  shotId: string,
  params?: { prompt?: string; model?: string; provider?: string }
): Promise<JobResponse> {
  const res = await api.post<JobResponse>(`/projects/${projectId}/shots/${shotId}/generate`, params || {});
  return res.data;
}

export async function createProject(data: ProjectCreate): Promise<ProjectDetail> {
  const res = await api.post<ProjectDetail>("/projects", data);
  return res.data;
}

export async function getProject(id: string): Promise<ProjectDetail> {
  const res = await api.get<ProjectDetail>(`/projects/${id}`);
  return res.data;
}

export async function listProjects(): Promise<ProjectSummary[]> {
  const res = await api.get<ProjectSummary[]>("/projects");
  return res.data;
}

export async function uploadAssets(
  projectId: string,
  files: {
    productImage?: File | null;
    logo?: File | null;
    music?: File | null;
  }
): Promise<ProjectDetail> {
  const formData = new FormData();
  if (files.productImage) {
    formData.append("product_image", files.productImage);
  }
  if (files.logo) {
    formData.append("logo", files.logo);
  }
  if (files.music) {
    formData.append("music", files.music);
  }

  const res = await api.post<ProjectDetail>(`/projects/${projectId}/uploads`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
}

export async function generateScript(projectId: string): Promise<JobResponse> {
  const res = await api.post<JobResponse>(`/projects/${projectId}/generate-script`);
  return res.data;
}

export async function approveStoryboard(
  projectId: string,
  model?: string,
  provider?: string
): Promise<JobResponse[]> {
  const payload = model ? { model, provider: provider || null } : {};
  const res = await api.post<JobResponse[]>(`/projects/${projectId}/approve`, payload);
  return res.data;
}

export async function retryShot(
  projectId: string,
  shotId: string,
  model?: string,
  provider?: string
): Promise<JobResponse> {
  const payload = model ? { model, provider: provider || null } : {};
  const res = await api.post<JobResponse>(`/projects/${projectId}/shots/${shotId}/retry`, payload);
  return res.data;
}

export async function generateTTS(projectId: string): Promise<JobResponse> {
  const res = await api.post<JobResponse>(`/projects/${projectId}/generate-tts`);
  return res.data;
}

export async function assembleVideo(projectId: string): Promise<JobResponse> {
  const res = await api.post<JobResponse>(`/projects/${projectId}/assemble`);
  return res.data;
}

export async function getTimeline(projectId: string): Promise<TimelineEditResponse> {
  const res = await api.get<TimelineEditResponse>(`/projects/${projectId}/timeline`);
  return res.data;
}

export async function saveTimeline(
  projectId: string,
  timelineData: TimelineData
): Promise<TimelineEditResponse> {
  const res = await api.put<TimelineEditResponse>(`/projects/${projectId}/timeline`, {
    timeline_data: timelineData,
  });
  return res.data;
}

export async function getTimelineHistory(
  projectId: string
): Promise<TimelineEditSummary[]> {
  const res = await api.get<TimelineEditSummary[]>(`/projects/${projectId}/timeline/history`);
  return res.data;
}

export async function exportTimeline(
  projectId: string,
  timelineEditId?: string
): Promise<JobResponse> {
  const res = await api.post<JobResponse>(`/projects/${projectId}/timeline/export`, {
    timeline_edit_id: timelineEditId || null,
  });
  return res.data;
}

export function getDownloadUrl(projectId: string): string {
  return `/api/projects/${projectId}/download`;
}

export function getArtifactUrl(pathOrKey: string): string {
  if (pathOrKey.startsWith("http")) return pathOrKey;
  // If absolute path like /data/artifacts/... extract relative part
  const clean = pathOrKey.replace(/^.*?artifacts\//, "");
  return `/api/artifacts/${clean}`;
}

export async function analyzeWebsite(url: string): Promise<WebsiteAnalysisResult> {
  const res = await api.post<WebsiteAnalysisResult>("/ai/analyze-website", { url });
  return res.data;
}

export async function generateCreativeBrief(
  payload: CreativeBriefRequest
): Promise<GeneratedBriefResponse> {
  const res = await api.post<GeneratedBriefResponse>("/ai/generate-brief", payload);
  return res.data;
}

export async function importWebsiteAsset(
  url: string,
  assetType: "product" | "logo",
  projectId?: string
): Promise<ImportAssetResponse> {
  const res = await api.post<ImportAssetResponse>("/ai/import-asset", {
    url,
    asset_type: assetType,
    project_id: projectId || null,
  });
  return res.data;
}


