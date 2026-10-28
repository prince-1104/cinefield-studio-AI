import axios from "axios";
import {
  JobResponse,
  ProjectCreate,
  ProjectDetail,
  ProjectSummary,
} from "../types";

const api = axios.create({
  baseURL: "/api",
});

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

export async function approveStoryboard(projectId: string): Promise<JobResponse[]> {
  const res = await api.post<JobResponse[]>(`/projects/${projectId}/approve`);
  return res.data;
}

export async function retryShot(projectId: string, shotId: string): Promise<JobResponse> {
  const res = await api.post<JobResponse>(`/projects/${projectId}/shots/${shotId}/retry`);
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

export function getDownloadUrl(projectId: string): string {
  return `/api/projects/${projectId}/download`;
}

export function getArtifactUrl(pathOrKey: string): string {
  if (pathOrKey.startsWith("http")) return pathOrKey;
  // If absolute path like /data/artifacts/... extract relative part
  const clean = pathOrKey.replace(/^.*?artifacts\//, "");
  return `/api/artifacts/${clean}`;
}
