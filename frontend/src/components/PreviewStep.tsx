import type { FC } from "react";
import { ProjectDetail } from "../types";
import { getArtifactUrl, getDownloadUrl } from "../api/client";

interface PreviewStepProps {
  project: ProjectDetail;
  onRestart: () => void;
}

export const PreviewStep: FC<PreviewStepProps> = ({
  project,
  onRestart,
}) => {
  const videoUrl = project.final_video_path
    ? getArtifactUrl(project.final_video_path)
    : "";
  const downloadUrl = getDownloadUrl(project.id);

  return (
    <div className="card final-player-card">
      <h2 className="card-title" style={{ justifyContent: "center", fontSize: "1.5rem" }}>
        🎉 Your Cinematic Advertisement is Ready!
      </h2>
      <p className="card-subtitle">
        Produced for <strong>{project.product_name}</strong> with Gemini Omni Flash video clips, OpenAI narration, and FFmpeg assembly.
      </p>

      {/* Video Player */}
      <div className="final-video-wrapper">
        {videoUrl ? (
          <video
            src={videoUrl}
            controls
            autoPlay
            playsInline
            style={{ width: "100%", maxHeight: "500px" }}
          />
        ) : (
          <div style={{ padding: "4rem 2rem", color: "var(--text-muted)" }}>
            Rendering video stream...
          </div>
        )}
      </div>

      {/* Actions */}
      <div style={{ display: "flex", justifyContent: "center", gap: "1rem", marginBottom: "2rem" }}>
        <a
          href={downloadUrl}
          className="btn btn-primary"
          style={{ textDecoration: "none" }}
          download
        >
          ⬇️ Download Finished MP4 Advertisement
        </a>
        <button className="btn btn-secondary" onClick={onRestart}>
          ➕ Create Another Advertisement
        </button>
      </div>

      {/* Campaign Details Summary */}
      <div
        style={{
          maxWidth: "800px",
          margin: "0 auto",
          background: "#0d141e",
          border: "1px solid var(--border-color)",
          borderRadius: "0.5rem",
          padding: "1.25rem",
          textAlign: "left",
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "1rem",
        }}
      >
        <div>
          <div className="shot-field-title">Campaign Name</div>
          <div className="shot-field-content">{project.product_name}</div>
        </div>
        <div>
          <div className="shot-field-title">Specifications</div>
          <div className="shot-field-content">1080p Full HD · 24 FPS · Stereo AAC</div>
        </div>
        <div>
          <div className="shot-field-title">Target Audience</div>
          <div className="shot-field-content">{project.audience}</div>
        </div>
        <div>
          <div className="shot-field-title">Call to Action</div>
          <div className="shot-field-content" style={{ color: "#60a5fa" }}>
            {project.cta}
          </div>
        </div>
        {project.script && (
          <div style={{ gridColumn: "span 2" }}>
            <div className="shot-field-title">Story Narrative</div>
            <div className="shot-field-content" style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
              {project.script}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
