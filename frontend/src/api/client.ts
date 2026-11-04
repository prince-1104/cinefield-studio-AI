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
  OverviewMetrics,
  ProviderMetric,
  ModelMetric,
  ModelSpec,
  ProjectCostMetric,
  ProjectDetailMetrics,
  PaginatedUsage,
} from "../types";

const api = axios.create({
  baseURL: "/api",
});

export async function getVideoModels(): Promise<VideoModelInfo[]> {
  const res = await api.get<VideoModelInfo[]>("/video-models");
  return res.data;
}

export async function getModels(
  capability?: string,
  includeUnavailable: boolean = true
): Promise<ModelSpec[]> {
  const params: Record<string, any> = { include_unavailable: includeUnavailable };
  if (capability) {
    params.capability = capability;
  }
  const res = await api.get<ModelSpec[]>("/models", { params });
  return res.data;
}

export async function getModelDetail(modelId: string): Promise<ModelSpec> {
  const res = await api.get<ModelSpec>(`/models/detail/${encodeURIComponent(modelId)}`);
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

// ---------------------------------------------------------------------------
// Centralized Admin AI Cost & Usage Analytics APIs
// ---------------------------------------------------------------------------

function getAdminHeaders(adminKey?: string): Record<string, string> {
  const key = adminKey || localStorage.getItem("pexyl_admin_key") || "pexyl-admin-secret-2026";
  return { "X-Admin-Key": key };
}

export async function getAdminOverview(
  range?: string,
  startDate?: string,
  endDate?: string,
  adminKey?: string,
  origin: string = "production"
): Promise<OverviewMetrics> {
  const res = await api.get<OverviewMetrics>("/admin/metrics/overview", {
    params: { range, start_date: startDate, end_date: endDate, origin },
    headers: getAdminHeaders(adminKey),
  });
  return res.data;
}

export async function getAdminProviders(
  range?: string,
  startDate?: string,
  endDate?: string,
  adminKey?: string,
  origin: string = "production"
): Promise<ProviderMetric[]> {
  const res = await api.get<ProviderMetric[]>("/admin/metrics/providers", {
    params: { range, start_date: startDate, end_date: endDate, origin },
    headers: getAdminHeaders(adminKey),
  });
  return res.data;
}

export async function getAdminModels(
  range?: string,
  startDate?: string,
  endDate?: string,
  adminKey?: string,
  origin: string = "production"
): Promise<ModelMetric[]> {
  const res = await api.get<ModelMetric[]>("/admin/metrics/models", {
    params: { range, start_date: startDate, end_date: endDate, origin },
    headers: getAdminHeaders(adminKey),
  });
  return res.data;
}

export async function getAdminProjects(
  range?: string,
  startDate?: string,
  endDate?: string,
  adminKey?: string,
  origin: string = "production"
): Promise<ProjectCostMetric[]> {
  const res = await api.get<ProjectCostMetric[]>("/admin/metrics/projects", {
    params: { range, start_date: startDate, end_date: endDate, origin },
    headers: getAdminHeaders(adminKey),
  });
  return res.data;
}

export async function getAdminProjectDetail(
  projectId: string,
  adminKey?: string,
  origin: string = "production"
): Promise<ProjectDetailMetrics> {
  const res = await api.get<ProjectDetailMetrics>(`/admin/metrics/projects/${projectId}`, {
    params: { origin },
    headers: getAdminHeaders(adminKey),
  });
  return res.data;
}

export async function getAdminUsageLedger(
  params: {
    projectId?: string;
    provider?: string;
    model?: string;
    operation?: string;
    requestStatus?: string;
    costStatus?: string;
    origin?: string;
    range?: string;
    startDate?: string;
    endDate?: string;
    limit?: number;
    offset?: number;
  },
  adminKey?: string
): Promise<PaginatedUsage> {
  const res = await api.get<PaginatedUsage>("/admin/usage", {
    params: {
      project_id: params.projectId || undefined,
      provider: params.provider || undefined,
      model: params.model || undefined,
      operation: params.operation || undefined,
      request_status: params.requestStatus || undefined,
      cost_status: params.costStatus || undefined,
      origin: params.origin || "production",
      range: params.range || undefined,
      start_date: params.startDate || undefined,
      end_date: params.endDate || undefined,
      limit: params.limit || 50,
      offset: params.offset || 0,
    },
    headers: getAdminHeaders(adminKey),
  });
  return res.data;
}

export async function downloadAdminUsageCsv(
  params: {
    projectId?: string;
    provider?: string;
    model?: string;
    origin?: string;
    range?: string;
    startDate?: string;
    endDate?: string;
  },
  adminKey?: string
): Promise<Blob> {
  const res = await api.get("/admin/usage/export-csv", {
    params: {
      project_id: params.projectId || undefined,
      provider: params.provider || undefined,
      model: params.model || undefined,
      origin: params.origin || "production",
      range: params.range || undefined,
      start_date: params.startDate || undefined,
      end_date: params.endDate || undefined,
    },
    headers: getAdminHeaders(adminKey),
    responseType: "blob",
  });
  return res.data;
}

export async function reconcileBilling(
  providerTaskId: string,
  actualCost: number,
  adminKey?: string
): Promise<{ success: boolean; message: string }> {
  const res = await api.post(
    "/admin/reconcile",
    { provider_task_id: providerTaskId, actual_cost: actualCost },
    { headers: getAdminHeaders(adminKey) }
  );
  return res.data;
}



