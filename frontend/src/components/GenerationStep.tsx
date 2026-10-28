import { useState, type FC } from "react";
import { ProjectDetail } from "../types";
import { ShotCard } from "./ShotCard";
import { assembleVideo, retryShot, getArtifactUrl } from "../api/client";
import {
  Clapperboard,
  CheckCircle2,
  Mic,
  Music,
  ArrowRight,
  Layers,
  Activity,
} from "lucide-react";

interface GenerationStepProps {
  project: ProjectDetail;
  onAssembled: (project: ProjectDetail) => void;
  onViewFinal: () => void;
  onError: (msg: string) => void;
}

export const GenerationStep: FC<GenerationStepProps> = ({
  project,
  onAssembled: _onAssembled,
  onViewFinal,
  onError,
}) => {
  const [retryingShotId, setRetryingShotId] = useState<string | null>(null);
  const [assembling, setAssembling] = useState(false);

  const totalShots = project.shots && project.shots.length > 0 ? project.shots.length : (project.shot_count || 8);
  const doneShotsCount = project.shots ? project.shots.filter((s) => s.status === "DONE").length : 0;
  const allShotsDone = totalShots > 0 && doneShotsCount === totalShots;
  const narrationReady = Boolean(project.narration_path);
  const isReadyToAssemble = allShotsDone && narrationReady;
  const isRendering = project.stage === "RENDERING" || assembling;
  const isAssembled = project.stage === "ASSEMBLED" && Boolean(project.final_video_path);

  const progressPercent = project.progress_percent || 0.0;
  const stageLabel = project.current_stage_label || "Synthesizing Production Components";

  const handleRetryShot = async (shotId: string) => {
    setRetryingShotId(shotId);
    try {
      await retryShot(project.id, shotId);
    } catch (err: any) {
      console.error("Failed to retry shot:", err);
      onError(
        err.response?.data?.detail || err.message || "Failed to retry shot generation"
      );
    } finally {
      setRetryingShotId(null);
    }
  };

  const handleAssemble = async () => {
    setAssembling(true);
    try {
      await assembleVideo(project.id);
      // Wait for background worker to compile and broadcast ASSEMBLED stage via SSE
    } catch (err: any) {
      console.error("Failed to trigger assembly:", err);
      onError(
        err.response?.data?.detail || err.message || "Failed to trigger final assembly"
      );
      setAssembling(false);
    }
  };

  return (
    <div className="generation-workspace">
      {/* Workspace Header */}
      <div className="workspace-header">
        <div className="workspace-title-row">
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <h1 className="workspace-heading">Production Monitor & Live Progress</h1>
            <span className="status-pill generating" style={{ fontSize: "0.75rem" }}>
              <Activity size={12} />
              <span>{progressPercent}% Complete</span>
            </span>
          </div>

          <div>
            {isAssembled ? (
              <button
                type="button"
                className="btn-primary-studio"
                onClick={onViewFinal}
              >
                <span>Open Customization Editor & Master</span>
                <ArrowRight size={16} />
              </button>
            ) : isRendering ? (
              <div
                className="btn-secondary-studio"
                style={{ opacity: 0.9, cursor: "wait", display: "inline-flex", alignItems: "center", gap: "0.5rem" }}
              >
                <div className="pulse-spinner" style={{ width: "16px", height: "16px", borderWidth: "2px" }} />
                <span>Compiling in FFmpeg...</span>
              </div>
            ) : isReadyToAssemble ? (
              <button
                type="button"
                className="btn-primary-studio"
                onClick={handleAssemble}
                disabled={assembling}
              >
                <Layers size={16} />
                <span>Assemble Final {project.target_duration}s Master</span>
              </button>
            ) : null}
          </div>
        </div>
        <p className="workspace-subheading">
          {stageLabel}. Gemini Omni Flash synthesizes all {totalShots} video clips in parallel while OpenAI generates synchronized narration.
        </p>
      </div>

      {/* Real Live Pipeline Progress Bar */}
      <div
        style={{
          background: "var(--bg-surface)",
          border: "1px solid var(--border-subtle)",
          borderRadius: "var(--radius-lg)",
          padding: "1rem 1.5rem",
          marginBottom: "1.75rem",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.6rem" }}>
          <div style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--text-main)" }}>
            {stageLabel}
          </div>
          <div style={{ fontSize: "0.85rem", fontWeight: 700, color: "#8b5cf6" }}>
            {progressPercent}%
          </div>
        </div>

        {/* Progress Track */}
        <div
          style={{
            width: "100%",
            height: "8px",
            backgroundColor: "var(--bg-surface-elevated)",
            borderRadius: "9999px",
            overflow: "hidden",
          }}
        >
          <div
            style={{
              width: `${Math.max(5, progressPercent)}%`,
              height: "100%",
              background: "linear-gradient(90deg, #7c3aed 0%, #38bdf8 100%)",
              borderRadius: "9999px",
              transition: "width 0.4s ease-out",
            }}
          />
        </div>
      </div>

      {/* Production Stats Bar */}
      <div className="production-stats-bar">
        <div className="stats-group">
          <div className="stat-metric">
            <div className="stat-metric-value">
              <Clapperboard size={18} style={{ color: "#8b5cf6" }} />
              <span>{doneShotsCount} / {totalShots}</span>
            </div>
            <span className="stat-metric-label">Clips Synthesized</span>
          </div>

          <div className="stat-metric">
            <div className="stat-metric-value">
              <Mic size={18} style={{ color: narrationReady ? "#10b981" : "#f59e0b" }} />
              <span>{narrationReady ? "Ready" : "Processing"}</span>
            </div>
            <span className="stat-metric-label">OpenAI Voiceover</span>
          </div>

          <div className="stat-metric">
            <div className="stat-metric-value">
              <Music size={18} style={{ color: project.music_path ? "#10b981" : "#64748b" }} />
              <span>{project.music_path ? "Attached" : "None"}</span>
            </div>
            <span className="stat-metric-label">Soundtrack Audio</span>
          </div>
        </div>

        <div>
          {!isAssembled && !isReadyToAssemble && (
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "var(--text-muted)", fontSize: "0.85rem" }}>
              <div className="pulse-spinner" style={{ width: "14px", height: "14px", borderWidth: "2px" }} />
              <span>Synthesizing Components...</span>
            </div>
          )}
        </div>
      </div>

      {/* Voiceover Track Panel if available */}
      {project.narration_path && (
        <div
          className="studio-panel"
          style={{
            marginBottom: "1.75rem",
            padding: "1rem 1.5rem",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "1rem",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <div className="asset-icon-circle" style={{ width: "36px", height: "36px" }}>
              <Mic size={18} />
            </div>
            <div>
              <div style={{ fontSize: "0.85rem", fontWeight: 600 }}>Master Voiceover Track</div>
              <div style={{ fontSize: "0.72rem", color: "var(--text-secondary)" }}>
                OpenAI Speech synthesis synchronized across all {totalShots} sequence scenes
              </div>
            </div>
          </div>
          <audio
            controls
            src={getArtifactUrl(project.narration_path)}
            style={{ height: "32px", maxWidth: "340px", width: "100%" }}
          />
        </div>
      )}

      {/* Multi-Shot Production Grid */}
      <div className="shots-filmstrip-grid">
        {project.shots.map((shot) => (
          <ShotCard
            key={shot.id}
            shot={shot}
            onRetry={handleRetryShot}
            isRetrying={retryingShotId === shot.id}
          />
        ))}
      </div>

      {/* Assembly Ready Banner */}
      {isReadyToAssemble && !isAssembled && (
        <div className="assembly-ready-banner">
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "#ffffff", fontWeight: 700, fontSize: "1.05rem", marginBottom: "0.3rem" }}>
              <CheckCircle2 size={20} style={{ color: "#34d399" }} />
              <span>All {totalShots} Video Clips & Audio Tracks Synthesized</span>
            </div>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", margin: 0 }}>
              The multi-layer FFmpeg rendering pipeline is ready to assemble normalized clips, synchronize captions, duck soundtrack behind speech, and apply watermark overlays into the final {project.target_duration}s master.
            </p>
          </div>
          <button
            type="button"
            className="btn-primary-studio"
            onClick={handleAssemble}
            disabled={assembling}
            style={{ padding: "0.85rem 1.75rem", fontSize: "0.95rem" }}
          >
            {assembling ? "Assembling in FFmpeg..." : `Assemble Final ${project.target_duration}s Master ➔`}
          </button>
        </div>
      )}
    </div>
  );
};
