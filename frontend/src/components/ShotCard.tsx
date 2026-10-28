import type { FC } from "react";
import { ShotResponse } from "../types";
import { getArtifactUrl } from "../api/client";
import {
  Sparkles,
  AlertCircle,
  RotateCw,
  Film,
  Camera,
  Mic,
  Clock,
} from "lucide-react";

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
  const getStatusClass = () => {
    switch (shot.status) {
      case "DONE":
        return "done";
      case "GENERATING":
      case "DOWNLOADING":
      case "VALIDATING":
      case "SUBMITTED":
        return "generating";
      case "FAILED":
        return "failed";
      default:
        return "pending";
    }
  };

  const getStatusLabel = () => {
    switch (shot.status) {
      case "DONE":
        return "✓ Done";
      case "SUBMITTED":
        return "Submitted";
      case "GENERATING":
        return "Synthesizing";
      case "DOWNLOADING":
        return "Downloading";
      case "VALIDATING":
        return "Validating";
      case "FAILED":
        return "Failed";
      default:
        return "Pending";
    }
  };

  const timeRange = `${shot.start_time.toFixed(1)}s – ${shot.end_time.toFixed(1)}s`;
  const durLabel = shot.actual_duration ? `${shot.actual_duration.toFixed(1)}s (actual)` : `${shot.target_duration.toFixed(1)}s`;

  return (
    <div className="shot-production-card">
      {/* Header */}
      <div className="shot-card-header">
        <div className="shot-role-pill">
          <Camera size={13} style={{ color: "#8b5cf6" }} />
          <span>Shot #{shot.shot_number}</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <span className="shot-timing-tag" title="Timeline window">
            <Clock size={10} style={{ display: "inline", marginRight: "3px" }} />
            {timeRange}
          </span>
          <span className={`status-pill ${getStatusClass()}`}>
            {getStatusLabel()}
          </span>
        </div>
      </div>

      {/* Viewport / Video Canvas */}
      <div
        className={`shot-viewport-area ${
          ["GENERATING", "DOWNLOADING", "VALIDATING"].includes(shot.status) ? "is-generating" : ""
        }`}
      >
        {shot.status === "DONE" && shot.video_path ? (
          <video
            src={getArtifactUrl(shot.video_path)}
            controls
            playsInline
            preload="metadata"
          />
        ) : ["GENERATING", "DOWNLOADING", "VALIDATING", "SUBMITTED"].includes(shot.status) ? (
          <div className="generating-pulse-indicator">
            <div className="pulse-spinner" />
            <span style={{ fontSize: "0.78rem", fontWeight: 600 }}>
              {shot.status === "DOWNLOADING"
                ? "Downloading clip from Gemini..."
                : shot.status === "VALIDATING"
                ? "Validating stream with ffprobe..."
                : "Gemini Omni Flash Synthesizing..."}
            </span>
          </div>
        ) : shot.status === "FAILED" ? (
          <div className="shot-viewport-placeholder" style={{ color: "#f87171" }}>
            <div
              className="shot-placeholder-icon"
              style={{
                backgroundColor: "rgba(239, 68, 68, 0.1)",
                borderColor: "rgba(239, 68, 68, 0.3)",
                color: "#f87171",
              }}
            >
              <AlertCircle size={22} />
            </div>
            <span style={{ fontSize: "0.8rem", fontWeight: 600 }}>
              Generation Interrupted
            </span>
          </div>
        ) : (
          <div className="shot-viewport-placeholder">
            <div className="shot-placeholder-icon">
              <Film size={22} />
            </div>
            <span style={{ fontSize: "0.78rem", color: "var(--text-secondary)" }}>
              Awaiting Production Approval ({durLabel})
            </span>
          </div>
        )}
      </div>

      {/* Card Body */}
      <div className="shot-card-body">
        {/* Description */}
        <div className="shot-field-group">
          <span className="shot-field-label">Action & Purpose</span>
          <div style={{ fontSize: "0.85rem", color: "var(--text-main)", lineHeight: 1.45 }}>
            {shot.description}
          </div>
        </div>

        {/* Visual Prompt */}
        <div className="shot-field-group">
          <span className="shot-field-label">Visual Synthesis Prompt</span>
          <div className="shot-prompt-box">
            {shot.visual_prompt}
          </div>
        </div>

        {/* Narration Voiceover */}
        {shot.narration_text && (
          <div className="shot-field-group">
            <span className="shot-field-label" style={{ display: "flex", alignItems: "center", gap: "0.3rem" }}>
              <Mic size={11} style={{ color: "#38bdf8" }} />
              <span>Voiceover Segment</span>
            </span>
            <div className="shot-narration-box">
              "{shot.narration_text}"
            </div>
          </div>
        )}

        {/* Error message */}
        {shot.error_message && (
          <div
            style={{
              background: "rgba(239, 68, 68, 0.1)",
              border: "1px solid rgba(239, 68, 68, 0.3)",
              color: "#fca5a5",
              borderRadius: "6px",
              padding: "0.5rem 0.65rem",
              fontSize: "0.75rem",
              display: "flex",
              alignItems: "flex-start",
              gap: "0.4rem",
            }}
          >
            <AlertCircle size={14} style={{ flexShrink: 0, marginTop: "2px" }} />
            <span>{shot.error_message}</span>
          </div>
        )}
      </div>

      {/* Footer & Actions */}
      <div className="shot-card-footer">
        <div style={{ display: "flex", alignItems: "center", gap: "0.45rem", fontSize: "0.72rem", color: "var(--text-secondary)" }}>
          <Sparkles size={12} style={{ color: "#8b5cf6" }} />
          <span>{shot.camera_motion || "Cinematic Motion"}</span>
          {shot.transition && <span>· {shot.transition}</span>}
          {shot.retry_count > 0 && <span>· Retries: {shot.retry_count}</span>}
        </div>

        {onRetry && (shot.status === "FAILED" || shot.status === "DONE") && (
          <button
            type="button"
            className="btn-secondary-studio"
            style={{ padding: "0.35rem 0.65rem", fontSize: "0.75rem" }}
            onClick={() => onRetry(shot.id)}
            disabled={isRetrying}
          >
            <RotateCw size={12} className={isRetrying ? "spin" : ""} />
            <span>{isRetrying ? "Retrying..." : "Regenerate Clip"}</span>
          </button>
        )}
      </div>
    </div>
  );
};
