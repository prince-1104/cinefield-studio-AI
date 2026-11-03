import { useEffect, useState, useRef } from "react";
import { ProjectDetail, GenerationProgressEvent } from "../types";
import { getProject } from "../api/client";

export function useProjectSSE(
  projectId: string | null,
  onUpdate?: (project: ProjectDetail) => void,
  onProgressEvent?: (evt: GenerationProgressEvent) => void
) {
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recentEvents, setRecentEvents] = useState<GenerationProgressEvent[]>([]);

  // Ref to hold current eventSource and reconnect timeout
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<any>(null);
  const isMountedRef = useRef(true);

  useEffect(() => {
    isMountedRef.current = true;

    if (!projectId) {
      setProject(null);
      setConnected(false);
      setRecentEvents([]);
      return;
    }

    // Always fetch latest authoritative state from PostgreSQL on initial hook mount or projectId change
    getProject(projectId)
      .then((data) => {
        if (isMountedRef.current) {
          setProject(data);
          if (onUpdate) onUpdate(data);
        }
      })
      .catch((err) => console.warn("Failed to fetch initial project state:", err));

    function connectSSE() {
      if (!projectId || !isMountedRef.current) return;

      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }

      const eventSource = new EventSource(`/api/projects/${projectId}/events`);
      eventSourceRef.current = eventSource;

      eventSource.onopen = () => {
        if (!isMountedRef.current) return;
        setConnected(true);
        setError(null);

        // Authoritative reconciliation after connection/reconnection
        getProject(projectId)
          .then((fresh) => {
            if (isMountedRef.current) {
              setProject(fresh);
              if (onUpdate) onUpdate(fresh);
            }
          })
          .catch(() => {});
      };

      // 1. Full snapshot updates
      eventSource.addEventListener("project_update", (event: MessageEvent) => {
        try {
          const data: ProjectDetail = JSON.parse(event.data);
          if (isMountedRef.current) {
            setProject(data);
            if (onUpdate) onUpdate(data);
          }
        } catch (err) {
          console.error("Failed to parse SSE project_update:", err);
        }
      });

      // 2. Granular live generation events
      eventSource.addEventListener("generation_progress", (event: MessageEvent) => {
        try {
          const progressEvt: GenerationProgressEvent = JSON.parse(event.data);
          if (isMountedRef.current) {
            setRecentEvents((prev) => [progressEvt, ...prev].slice(0, 30));
            if (onProgressEvent) onProgressEvent(progressEvt);
          }
        } catch (err) {
          console.error("Failed to parse SSE generation_progress:", err);
        }
      });

      eventSource.addEventListener("ping", () => {
        // Keepalive heartbeat
      });

      eventSource.onerror = (err) => {
        if (!isMountedRef.current) return;
        console.warn("SSE connection interrupted, reconciling from DB & reconnecting...", err);
        setConnected(false);
        setError("Reconnecting to live production feed...");

        eventSource.close();
        // Exponential backoff / quick retry
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = setTimeout(() => {
          connectSSE();
        }, 3000);
      };
    }

    connectSSE();

    return () => {
      isMountedRef.current = false;
      clearTimeout(reconnectTimeoutRef.current);
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
      setConnected(false);
    };
  }, [projectId]);

  return { project, connected, error, recentEvents, setProject };
}
