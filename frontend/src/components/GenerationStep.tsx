import { useState, useEffect, type FC } from "react";
import { ProjectDetail, VideoModelInfo } from "../types";
import { ShotCard } from "./ShotCard";
import {
  assembleVideo,
  retryShot,
  getArtifactUrl,
  getVideoModels,
  selectProjectModel,
  generateShotVideo,
  approveStoryboard,
} from "../api/client";
import {
  Clapperboard,
  CheckCircle2,
  Mic,
  Music,
  ArrowRight,
  Layers,
  Activity,
  Cpu,
  Play,
  RotateCw,
  Sparkles,
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
  const [generatingAll, setGeneratingAll] = useState(false);
  const [models, setModels] = useState<VideoModelInfo[]>([]);
  const [selectedModelId, setSelectedModelId] = useState<string>(
    project.selected_video_model || "seedance-1-0-pro-250528"
  );
  const [switchingModel, setSwitchingModel] = useState(false);

  useEffect(() => {
    getVideoModels()
      .then((data) => {
        setModels(data);
        if (project.selected_video_model) {
          setSelectedModelId(project.selected_video_model);
        } else if (data.length > 0) {
          const defaultModel = data.find((m) => m.is_default) || data[0];
          if (defaultModel) {
            setSelectedModelId(defaultModel.id);
          }
        }
      })
      .catch((err) => console.warn("Failed to fetch available video models:", err));
  }, [project.selected_video_model]);

  const selectedModel = models.find((m) => m.id === selectedModelId) || {
    id: selectedModelId,
    name: selectedModelId.includes("seedance") ? "Seedance 1.0 Pro" : "Gemini Omni Flash 1.1",
    provider: selectedModelId.includes("seedance") ? "seedance" : "gemini",
    provider_name: selectedModelId.includes("seedance") ? "ByteDance Seedance" : "Google DeepMind",
    description: "Cinematic AI video generation model with temporal consistency and camera motion physics.",
    capabilities: ["1080p Resolution", "First-Frame Image Conditioning", "Camera Motion Control"],
  };

  const handleModelChange = async (newModelId: string) => {
    setSelectedModelId(newModelId);
    setSwitchingModel(true);
    try {
      const found = models.find((m) => m.id === newModelId);
      await selectProjectModel(project.id, newModelId, found?.provider);
    } catch (err: any) {
      console.error("Failed to select video model:", err);
      onError(err.response?.data?.detail || err.message || "Failed to switch video model");
    } finally {
      setSwitchingModel(false);
    }
  };

  const totalShots = project.shots && project.shots.length > 0 ? project.shots.length : (project.shot_count || 8);
  const doneShotsCount = project.shots ? project.shots.filter((s) => s.status === "DONE").length : 0;
  const pendingShotsCount = project.shots ? project.shots.filter((s) => s.status === "PENDING" || s.status === "FAILED").length : 0;
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
      await retryShot(project.id, shotId, selectedModelId, selectedModel.provider);
    } catch (err: any) {
      console.error("Failed to retry shot:", err);
      onError(err.response?.data?.detail || err.message || "Failed to retry shot generation");
    } finally {
      setRetryingShotId(null);
    }
  };

  const handleGenerateSingleShot = async (shotId: string, prompt?: string) => {
    setRetryingShotId(shotId);
    try {
      await generateShotVideo(project.id, shotId, {
        prompt,
        model: selectedModelId,
        provider: selectedModel.provider,
      });
    } catch (err: any) {
      console.error("Failed to generate shot:", err);
      onError(err.response?.data?.detail || err.message || "Failed to generate shot");
    } finally {
      setRetryingShotId(null);
    }
  };

  const handleGenerateAllShots = async () => {
    setGeneratingAll(true);
    try {
      await approveStoryboard(project.id, selectedModelId, selectedModel.provider);
    } catch (err: any) {
      console.error("Failed to generate all shots:", err);
      onError(err.response?.data?.detail || err.message || "Failed to generate shots");
    } finally {
      setGeneratingAll(false);
    }
  };

  const handleAssemble = async () => {
    setAssembling(true);
    try {
      await assembleVideo(project.id);
    } catch (err: any) {
      console.error("Failed to trigger assembly:", err);
      onError(err.response?.data?.detail || err.message || "Failed to trigger final assembly");
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

          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            {pendingShotsCount > 0 && !isAssembled && !isRendering && (
              <button
                type="button"
                className="btn-secondary-studio"
                onClick={handleGenerateAllShots}
                disabled={generatingAll}
                style={{ padding: "0.55rem 1rem", fontSize: "0.85rem" }}
              >
                {generatingAll ? (
                  <>
                    <RotateCw size={14} className="spin" />
                    <span>Queuing Generation...</span>
                  </>
                ) : (
                  <>
                    <Play size={14} />
                    <span>Generate Remaining {pendingShotsCount} Clips</span>
                  </>
                )}
              </button>
            )}

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
          {stageLabel}. {selectedModel.name} synthesizes clips with multimodal continuity while OpenAI generates synchronized narration.
        </p>
      </div>

      {/* Model Selection Hero Panel */}
      <div className="model-selection-hero">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "1rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
            <div className="asset-icon-circle" style={{ width: "34px", height: "34px", backgroundColor: "rgba(124, 58, 237, 0.15)" }}>
              <Cpu size={18} style={{ color: "#a78bfa" }} />
            </div>
            <div>
              <div style={{ fontSize: "0.95rem", fontWeight: 700, color: "#ffffff" }}>
                AI Video Generation Model Engine
              </div>
              <div style={{ fontSize: "0.78rem", color: "#94a3b8" }}>
                Select generative model for multi-shot clip synthesis with temporal consistency
              </div>
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
            <span style={{ fontSize: "0.78rem", fontWeight: 600, color: "#cbd5e1" }}>
              Engine Dropdown:
            </span>
            <select
              value={selectedModelId}
              onChange={(e) => handleModelChange(e.target.value)}
              disabled={switchingModel}
              style={{
                background: "var(--bg-surface-elevated)",
                border: "1px solid var(--border-default)",
                color: "#ffffff",
                padding: "0.4rem 0.85rem",
                borderRadius: "6px",
                fontSize: "0.82rem",
                fontWeight: 600,
                outline: "none",
                cursor: "pointer",
              }}
            >
              {models.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name} ({m.provider_name})
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Quick Model Pill Buttons */}
        {models.length > 0 && (
          <div className="model-pill-tabs">
            {models.map((m) => (
              <button
                key={m.id}
                type="button"
                className={`model-pill-btn ${selectedModelId === m.id ? "active" : ""}`}
                onClick={() => handleModelChange(m.id)}
                disabled={switchingModel}
                title={m.description}
              >
                <Cpu size={14} style={{ color: selectedModelId === m.id ? "#c4b5fd" : "#94a3b8" }} />
                <span>{m.name}</span>
                {m.is_default && (
                  <span style={{ fontSize: "0.65rem", padding: "0.1rem 0.35rem", borderRadius: "9999px", background: "rgba(139, 92, 246, 0.3)", color: "#ffffff" }}>
                    Default
                  </span>
                )}
              </button>
            ))}
          </div>
        )}

        {/* Selected Model Details & Capabilities */}
        <div className="model-active-meta-card">
          <div style={{ maxWidth: "640px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", marginBottom: "0.3rem" }}>
              <span style={{ fontSize: "0.92rem", fontWeight: 700, color: "#ffffff" }}>
                {selectedModel.name}
              </span>
              <span
                style={{
                  fontSize: "0.7rem",
                  background: "rgba(139, 92, 246, 0.25)",
                  border: "1px solid rgba(139, 92, 246, 0.4)",
                  color: "#ddd6fe",
                  padding: "0.15rem 0.5rem",
                  borderRadius: "4px",
                  fontWeight: 600,
                }}
              >
                {selectedModel.provider_name}
              </span>
            </div>
            <p style={{ fontSize: "0.82rem", color: "#cbd5e1", margin: 0, lineHeight: 1.45 }}>
              {selectedModel.description}
            </p>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "0.45rem", flexWrap: "wrap" }}>
            {(selectedModel.capabilities || []).map((cap, i) => (
              <span key={i} className="model-chip-tag">
                <Sparkles size={11} style={{ color: "#8b5cf6" }} />
                <span>{cap}</span>
              </span>
            ))}
          </div>
        </div>
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
            onGenerateShot={handleGenerateSingleShot}
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
