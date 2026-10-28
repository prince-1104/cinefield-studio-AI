import type { FC } from "react";
import { ShotResponse } from "../types";
import { getArtifactUrl } from "../api/client";

interface ShotCardProps {
  shot: ShotResponse;
  onRetry?: (shotId: string) => void;
  isRetrying?: boolean;
}

export const ShotCard: FC<ShotCardProps> = ({
  shot,
  onRetry,
  isRetrying,
}) => {
  const titles = [
    "Shot 1: The Hook",
    "Shot 2: The Reveal",
    "Shot 3: The Climax & CTA",
  ];
  const title = titles[shot.shot_number - 1] || `Shot ${shot.shot_number}`;

  const statusClass = `status-${shot.status.toLowerCase()}`;

  return (
    <div className="shot-card">
      <div className="shot-header">
        <span className="shot-tag">{title}</span>
        <span className={`status-badge ${statusClass}`}>{shot.status}</span>
      </div>

      <div className="shot-body">
        {/* Video Player or Placeholder */}
        <div className="shot-video-container">
          {shot.status === "DONE" && shot.video_path ? (
            <video
              src={getArtifactUrl(shot.video_path)}
              controls
              playsInline
              preload="metadata"
            />
          ) : shot.status === "GENERATING" ? (
            <div style={{ textAlign: "center", color: "#f59e0b" }}>
              <div style={{ fontSize: "1.5rem", marginBottom: "0.25rem" }}>⚡</div>
              <p style={{ fontSize: "0.8rem", fontWeight: 600 }}>
                Generating with Gemini Omni Flash...
              </p>
            </div>
          ) : shot.status === "FAILED" ? (
            <div style={{ textAlign: "center", color: "#ef4444", padding: "1rem" }}>
              <div style={{ fontSize: "1.5rem", marginBottom: "0.25rem" }}>⚠️</div>
              <p style={{ fontSize: "0.8rem" }}>Generation Failed</p>
            </div>
          ) : (
            <div style={{ textAlign: "center", color: "var(--text-muted)" }}>
              <div style={{ fontSize: "1.5rem", marginBottom: "0.25rem" }}>🎬</div>
              <p style={{ fontSize: "0.75rem" }}>Pending Approval</p>
            </div>
          )}
        </div>

        <div>
          <div className="shot-field-title">Description</div>
          <div className="shot-field-content">{shot.description}</div>
        </div>

        <div>
          <div className="shot-field-title">Visual Prompt</div>
          <div
            className="shot-field-content"
            style={{ fontSize: "0.82rem", color: "var(--text-secondary)" }}
          >
            {shot.visual_prompt}
          </div>
        </div>

        {shot.narration_text && (
          <div>
            <div className="shot-field-title">Narration Line</div>
            <div
              className="shot-field-content"
              style={{ fontStyle: "italic", color: "#60a5fa" }}
            >
              "{shot.narration_text}"
            </div>
          </div>
        )}

        {shot.error_message && (
          <div
            style={{
              background: "rgba(239, 68, 68, 0.1)",
              border: "1px solid #ef4444",
              color: "#fca5a5",
              borderRadius: "0.3rem",
              padding: "0.5rem",
              fontSize: "0.75rem",
            }}
          >
            <strong>Error:</strong> {shot.error_message}
          </div>
        )}
      </div>

      <div className="shot-footer">
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", width: "100%", justifyContent: "space-between" }}>
          <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
            {shot.retry_count > 0 && `Retries: ${shot.retry_count}`}
          </span>
          {onRetry && (shot.status === "FAILED" || shot.status === "DONE") && (
            <button
              className="btn btn-secondary"
              style={{ padding: "0.35rem 0.75rem", fontSize: "0.8rem" }}
              onClick={() => onRetry(shot.id)}
              disabled={isRetrying}
            >
              {isRetrying ? "Retrying..." : "Retry Shot"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
