import { useState, type FC } from "react";
import { ShotResponse } from "../types";
import { getArtifactUrl, updateShotPrompt } from "../api/client";
import {
  Sparkles,
  AlertCircle,
  RotateCw,
  Film,
  Camera,
  Mic,
  Clock,
  Edit3,
  Check,
  X,
  Download,
  Cpu,
  Play,
} from "lucide-react";

interface ShotCardProps {
  shot: ShotResponse;
  onRetry?: (shotId: string) => void;
  onGenerateShot?: (shotId: string, prompt?: string) => void;
  onPromptUpdated?: (shotId: string, newPrompt: string) => void;
  isRetrying?: boolean;
}

export const ShotCard: FC<ShotCardProps> = ({
  shot,
  onRetry,
  onGenerateShot,
  onPromptUpdated,
  isRetrying,
}) => {
  const [isEditingPrompt, setIsEditingPrompt] = useState(false);
  const [promptText, setPromptText] = useState(shot.visual_prompt);
  const [savingPrompt, setSavingPrompt] = useState(false);

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

  const handleSavePrompt = async () => {
    setSavingPrompt(true);
    try {
      await updateShotPrompt(shot.project_id, shot.id, promptText);
      setIsEditingPrompt(false);
      if (onPromptUpdated) {
        onPromptUpdated(shot.id, promptText);
      }
    } catch (err) {
      console.error("Failed to update visual prompt:", err);
    } finally {
      setSavingPrompt(false);
    }
  };

  const handleCancelPrompt = () => {
    setPromptText(shot.visual_prompt);
    setIsEditingPrompt(false);
  };

  const timeRange = `${shot.start_time.toFixed(1)}s – ${shot.end_time.toFixed(1)}s`;
  const durLabel = shot.actual_duration
    ? `${shot.actual_duration.toFixed(1)}s (actual)`
    : `${shot.target_duration.toFixed(1)}s`;

  const modelLabel = shot.model
    ? shot.model.replace("seedance-1-0-pro-250528", "Seedance 1.0 Pro")
        .replace("seedance-1-0-pro-fast-251015", "Seedance 1.0 Fast")
        .replace("dreamina-seedance-2-0-260128", "Seedance 2.0")
        .replace("gemini-omni-1.1-flash", "Gemini Omni Flash")
    : (shot.provider === "gemini" ? "Gemini Omni Flash" : "Seedance 1.0 Pro");

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
                ? `Downloading clip from ${shot.provider === "gemini" ? "Gemini" : "Seedance"}...`
                : shot.status === "VALIDATING"
                ? "Validating stream with ffprobe..."
                : `${modelLabel} Synthesizing...`}
            </span>
            {shot.provider_job_id && (
              <span style={{ fontSize: "0.68rem", opacity: 0.7, fontFamily: "monospace" }}>
                Task: {shot.provider_job_id.slice(0, 16)}...
              </span>
            )}
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
              Ready for {modelLabel} ({durLabel})
            </span>
          </div>
        )}
      </div>

      {/* Card Body */}
      <div className="shot-card-body">
        {/* Model Tag */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.5rem" }}>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "0.35rem",
              background: "rgba(99, 102, 241, 0.1)",
              border: "1px solid rgba(99, 102, 241, 0.25)",
              color: "#a5b4fc",
              padding: "0.2rem 0.5rem",
              borderRadius: "4px",
              fontSize: "0.72rem",
              fontWeight: 600,
            }}
          >
            <Cpu size={11} />
            <span>{modelLabel}</span>
          </div>

          {!isEditingPrompt && (
            <button
              type="button"
              className="btn-secondary-studio"
              style={{ padding: "0.2rem 0.5rem", fontSize: "0.7rem", gap: "0.25rem" }}
              onClick={() => setIsEditingPrompt(true)}
              title="Edit visual prompt"
            >
              <Edit3 size={11} />
              <span>Edit Prompt</span>
            </button>
          )}
        </div>

        {/* Action & Purpose Description */}
        <div className="shot-field-group">
          <span className="shot-field-label">Action & Purpose</span>
          <div style={{ fontSize: "0.85rem", color: "var(--text-main)", lineHeight: 1.45 }}>
            {shot.description}
          </div>
        </div>

        {/* Visual Prompt (with inline editor) */}
        <div className="shot-field-group">
          <span className="shot-field-label">Visual Synthesis Prompt</span>
          {isEditingPrompt ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem" }}>
              <textarea
                value={promptText}
                onChange={(e) => setPromptText(e.target.value)}
                rows={3}
                style={{
                  width: "100%",
                  background: "var(--bg-surface-elevated)",
                  border: "1px solid #8b5cf6",
                  color: "var(--text-main)",
                  borderRadius: "6px",
                  padding: "0.5rem",
                  fontSize: "0.8rem",
                  fontFamily: "inherit",
                  resize: "vertical",
                }}
              />
              <div style={{ display: "flex", gap: "0.4rem", justifyContent: "flex-end" }}>
                <button
                  type="button"
                  className="btn-secondary-studio"
                  style={{ padding: "0.25rem 0.5rem", fontSize: "0.72rem" }}
                  onClick={handleCancelPrompt}
                >
                  <X size={11} />
                  <span>Cancel</span>
                </button>
                <button
                  type="button"
                  className="btn-primary-studio"
                  style={{ padding: "0.25rem 0.65rem", fontSize: "0.72rem" }}
                  onClick={handleSavePrompt}
                  disabled={savingPrompt}
                >
                  <Check size={11} />
                  <span>{savingPrompt ? "Saving..." : "Save Prompt"}</span>
                </button>
              </div>
            </div>
          ) : (
            <div className="shot-prompt-box">
              {shot.visual_prompt}
            </div>
          )}
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

        <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
          {/* Direct Download button for completed clip */}
          {shot.status === "DONE" && shot.video_path && (
            <a
              href={getArtifactUrl(shot.video_path)}
              download={`shot_${shot.shot_number}.mp4`}
              className="btn-secondary-studio"
              style={{ padding: "0.35rem 0.65rem", fontSize: "0.75rem", textDecoration: "none" }}
              title="Download individual shot MP4"
            >
              <Download size={12} />
              <span>Clip MP4</span>
            </a>
          )}

          {/* Generate button if pending */}
          {shot.status === "PENDING" && onGenerateShot && (
            <button
              type="button"
              className="btn-primary-studio"
              style={{ padding: "0.35rem 0.65rem", fontSize: "0.75rem" }}
              onClick={() => onGenerateShot(shot.id, promptText)}
              disabled={isRetrying}
            >
              <Play size={12} />
              <span>Generate Clip</span>
            </button>
          )}

          {/* Regenerate button if failed or done */}
          {onRetry && (shot.status === "FAILED" || shot.status === "DONE") && (
            <button
              type="button"
              className="btn-secondary-studio"
              style={{ padding: "0.35rem 0.65rem", fontSize: "0.75rem" }}
              onClick={() => onRetry(shot.id)}
              disabled={isRetrying}
            >
              <RotateCw size={12} className={isRetrying ? "spin" : ""} />
              <span>{isRetrying ? "Generating..." : "Regenerate Clip"}</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
