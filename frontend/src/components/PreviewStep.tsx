import type { FC } from "react";
import { ProjectDetail } from "../types";
import { getArtifactUrl, getDownloadUrl } from "../api/client";
import {
  Download,
  Plus,
  ArrowLeft,
  Tv,
  Volume2,
  Film,
  Sparkles,
  CheckCircle2,
} from "lucide-react";

interface PreviewStepProps {
  project: ProjectDetail;
  onRestart: () => void;
  onBackToProduction: () => void;
}

export const PreviewStep: FC<PreviewStepProps> = ({
  project,
  onRestart,
  onBackToProduction,
}) => {
  const videoUrl = project.final_video_path
    ? getArtifactUrl(project.final_video_path)
    : "";
  const downloadUrl = getDownloadUrl(project.id);

  const meta = project.video_metadata;
  const durationText = meta?.duration ? `${meta.duration.toFixed(1)}s (measured)` : `${project.target_duration}s (target)`;
  const resolutionText = meta ? `${meta.width} × ${meta.height} (${meta.fps} FPS)` : (
    project.aspect_ratio === "9:16" ? "1080 × 1920 (24 FPS)" : "1920 × 1080 (24 FPS)"
  );
  const shotCount = project.shots ? project.shots.length : project.shot_count;

  return (
    <div className="preview-workspace">
      {/* Workspace Header */}
      <div className="workspace-header">
        <div className="workspace-title-row">
          <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
            <h1 className="workspace-heading">Cinema Master Delivery</h1>
            <span className="status-pill done" style={{ fontSize: "0.75rem" }}>
              <CheckCircle2 size={12} />
              <span>Production Complete · {durationText}</span>
            </span>
          </div>

          <div style={{ display: "flex", gap: "0.75rem" }}>
            <button
              type="button"
              className="btn-secondary-studio"
              onClick={onBackToProduction}
              style={{ fontSize: "0.8rem", padding: "0.45rem 0.85rem" }}
            >
              <ArrowLeft size={14} />
              <span>Production Monitor</span>
            </button>
            <button
              type="button"
              className="btn-secondary-studio"
              onClick={onRestart}
              style={{ fontSize: "0.8rem", padding: "0.45rem 0.85rem" }}
            >
              <Plus size={14} />
              <span>New Campaign</span>
            </button>
          </div>
        </div>
        <p className="workspace-subheading">
          Final cinema advertisement for <strong>{project.product_name}</strong> rendered across {shotCount} sequence scenes with Gemini Omni Flash clips, OpenAI narration, dynamic FFmpeg audio ducking, and watermark overlays.
        </p>
      </div>

      {/* Cinema Theater Stage Canvas */}
      <div className="cinema-theater-container">
        <div className="theater-stage-canvas">
          <div className="theater-player-frame">
            {videoUrl ? (
              <video
                src={videoUrl}
                controls
                autoPlay
                playsInline
                preload="auto"
              />
            ) : (
              <div style={{ padding: "6rem 2rem", color: "var(--text-muted)", textAlign: "center" }}>
                <Film size={40} style={{ opacity: 0.4, marginBottom: "0.75rem" }} />
                <p>Synthesizing cinema master video stream...</p>
              </div>
            )}
          </div>

          <div className="theater-control-strip">
            <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
              <span style={{ fontSize: "1rem", fontWeight: 700, color: "var(--text-main)" }}>
                {project.product_name} · {project.target_duration}s Cinema Master
              </span>
              <span className="asset-format-tag">H.264 / AAC MP4</span>
            </div>

            <div className="theater-actions-bar">
              <a
                href={downloadUrl}
                className="btn-primary-studio"
                style={{ textDecoration: "none" }}
                download
              >
                <Download size={16} />
                <span>Download Master MP4</span>
              </a>
            </div>
          </div>
        </div>

        {/* Delivery Specifications Grid */}
        <div className="delivery-specs-grid">
          <div className="spec-tile">
            <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", color: "var(--text-muted)" }}>
              <Tv size={14} />
              <span className="spec-tile-title">Master Output</span>
            </div>
            <span className="spec-tile-value">{resolutionText}</span>
          </div>

          <div className="spec-tile">
            <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", color: "var(--text-muted)" }}>
              <Volume2 size={14} />
              <span className="spec-tile-title">Audio Pipeline</span>
            </div>
            <span className="spec-tile-value">Stereo AAC · Ducked Mix</span>
          </div>

          <div className="spec-tile">
            <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", color: "var(--text-muted)" }}>
              <Sparkles size={14} />
              <span className="spec-tile-title">Visual Synthesizer</span>
            </div>
            <span className="spec-tile-value">Gemini Omni Flash</span>
          </div>

          <div className="spec-tile">
            <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", color: "var(--text-muted)" }}>
              <Film size={14} />
              <span className="spec-tile-title">Sequence Structure</span>
            </div>
            <span className="spec-tile-value">{shotCount}-Shot Arc ({durationText})</span>
          </div>
        </div>

        {/* Narrative & Campaign Strategy Details */}
        <div
          className="studio-panel"
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "1.5rem",
          }}
        >
          <div>
            <div className="shot-field-label" style={{ marginBottom: "0.3rem" }}>Campaign Audience</div>
            <div style={{ fontSize: "0.9rem", color: "var(--text-main)" }}>
              {project.audience}
            </div>
          </div>

          <div>
            <div className="shot-field-label" style={{ marginBottom: "0.3rem" }}>Call to Action (CTA)</div>
            <div style={{ fontSize: "0.95rem", fontWeight: 600, color: "#38bdf8" }}>
              {project.cta}
            </div>
          </div>

          {project.script && (
            <div style={{ gridColumn: "span 2", borderTop: "1px solid var(--border-subtle)", paddingTop: "1rem" }}>
              <div className="shot-field-label" style={{ marginBottom: "0.3rem" }}>Narrative Script Arc</div>
              <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)", lineHeight: 1.6 }}>
                {project.script}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
