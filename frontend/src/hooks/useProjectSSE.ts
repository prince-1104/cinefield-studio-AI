import { useEffect, useState } from "react";
import { ProjectDetail } from "../types";

export function useProjectSSE(
  projectId: string | null,
  onUpdate?: (project: ProjectDetail) => void
) {
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!projectId) {
      setProject(null);
      setConnected(false);
      return;
    }

    const eventSource = new EventSource(`/api/projects/${projectId}/events`);

    eventSource.onopen = () => {
      setConnected(true);
      setError(null);
    };

    eventSource.addEventListener("project_update", (event: MessageEvent) => {
      try {
        const data: ProjectDetail = JSON.parse(event.data);
        setProject(data);
        if (onUpdate) {
          onUpdate(data);
        }
      } catch (err) {
        console.error("Failed to parse SSE project_update:", err);
      }
    });

    eventSource.addEventListener("ping", () => {
      // Keepalive heartbeat
    });

    eventSource.onerror = (err) => {
      console.warn("SSE connection interrupted, retrying...", err);
      setConnected(false);
      setError("Connecting to live updates...");
    };

    return () => {
      eventSource.close();
      setConnected(false);
    };
  }, [projectId]);

  return { project, connected, error, setProject };
}

