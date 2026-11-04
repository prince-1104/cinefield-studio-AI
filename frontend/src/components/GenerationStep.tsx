import { useState, useEffect, type FC } from "react";
import { ProjectDetail, VideoModelInfo, GenerationProgressEvent } from "../types";
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
  CheckCircle2,
  Mic,
  Layers,
  Activity,
  Cpu,
  Play,
  RotateCw,
  Sparkles,
  AlertCircle,
  Download,
  Terminal,
  ChevronDown,
  ChevronUp,
  Clock,
  Film,
} from "lucide-react";

interface GenerationStepProps {
  project: ProjectDetail;
  onAssembled: (project: ProjectDetail) => void;
  onViewFinal: () => void;
  onError: (msg: string) => void;
  liveEvents?: GenerationProgressEvent[];
}

export const GenerationStep: FC<GenerationStepProps> = ({
  project,
  onAssembled: _onAssembled,
  onViewFinal,
  onError,
  liveEvents = [],
}) => {
  const [retryingShotId, setRetryingShotId] = useState<string | null>(null);
  const [assembling, setAssembling] = useState(false);
  const [generatingAll, setGeneratingAll] = useState(false);
  const [models, setModels] = useState<VideoModelInfo[]>([]);
  const [selectedModelId, setSelectedModelId] = useState<string>(
    project.selected_video_model || ""
  );
  const [switchingModel, setSwitchingModel] = useState(false);
  const [eventsDrawerOpen, setEventsDrawerOpen] = useState(false);

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
    name: selectedModelId.includes("2-5")
      ? "Seedance 2.5 Industrial"
      : selectedModelId.includes("seedance")
      ? "Seedance 1.0 Pro"
      : "Gemini Omni Flash 1.1",
    provider: selectedModelId.includes("seedance") ? "seedance" : "gemini",
    provider_name: selectedModelId.includes("seedance") ? "ByteDance Seedance" : "Google DeepMind",
    description: "Cinematic AI video generation model with temporal consistency and camera motion physics.",
    capabilities: ["1080p Resolution", "First-Frame Image Conditioning", "Camera Motion Control"],
    is_available: true,
    unavailability_reason: null,
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

  // Real-time Shot and Assembly States Aggregation
  const totalShots = project.shots && project.shots.length > 0 ? project.shots.length : (project.shot_count || 8);
  const doneShotsCount = project.shots ? project.shots.filter((s) => s.status === "DONE" || s.status === "COMPLETED").length : 0;
  const generatingShotsCount = project.shots ? project.shots.filter((s) => ["GENERATING", "DOWNLOADING", "VALIDATING", "SUBMITTED", "CLAIMED"].includes(s.status)).length : 0;
  const queuedShotsCount = project.shots ? project.shots.filter((s) => ["PENDING", "QUEUED"].includes(s.status)).length : 0;
  const failedShotsCount = project.shots ? project.shots.filter((s) => s.status === "FAILED").length : 0;
  const retryingShotsCount = project.shots ? project.shots.filter((s) => s.status === "RETRYING").length : 0;

  const allShotsDone = totalShots > 0 && doneShotsCount === totalShots;
  const narrationReady = Boolean(project.narration_path);

  // Distinct Video Generation Progress
  const videoProgressPercent = totalShots > 0 ? Math.round((doneShotsCount / totalShots) * 100) : 0;

  // Distinct Assembly States
  const isAssemblyQueued = project.stage === "ASSEMBLY_QUEUED";
  const isAssembling = project.stage === "ASSEMBLING" || project.stage === "RENDERING" || assembling;
  const isAssembled = project.stage === "ASSEMBLED" && Boolean(project.final_video_path);
  const isAssemblyFailed = project.stage === "ASSEMBLY_FAILED";
  const isReadyToAssemble = allShotsDone && narrationReady && !isAssembled && !isAssembling;

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

  const handleRetryAllFailed = async () => {
    if (!project.shots) return;
    const failed = project.shots.filter((s) => s.status === "FAILED");
    for (const f of failed) {
      handleRetryShot(f.id);
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
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", flexWrap: "wrap" }}>
            <h1 className="workspace-heading">Production Monitor & Live Progress</h1>
            <span className="status-pill generating" style={{ fontSize: "0.78rem" }}>
              <Activity size={13} />
              <span>{project.progress_percent}% Production Pipeline</span>
            </span>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", flexWrap: "wrap" }}>
            {/* Retry Failed button */}
            {failedShotsCount > 0 && (
              <button
                type="button"
                className="btn-secondary-studio"
                onClick={handleRetryAllFailed}
                style={{ borderColor: "rgba(239, 68, 68, 0.4)", color: "#f87171", padding: "0.5rem 0.85rem" }}
              >
                <RotateCw size={13} />
                <span>Retry {failedShotsCount} Failed Shots</span>
              </button>
            )}

            {/* Generate Remaining button */}
            {queuedShotsCount > 0 && !isAssembled && !isAssembling && (
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
                    <span>Generate Remaining {queuedShotsCount} Clips</span>
                  </>
                )}
              </button>
            )}

            {/* Assemble / Ready CTA */}
            {isAssembled ? (
              <button
                type="button"
                className="btn-primary-studio"
                onClick={onViewFinal}
                style={{ padding: "0.55rem 1.15rem", background: "linear-gradient(135deg, #10b981 0%, #059669 100%)" }}
              >
                <CheckCircle2 size={16} />
                <span>Preview Master Video</span>
              </button>
            ) : isAssembling ? (
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

      {/* =========================================================================
          Real-Time Video Generation & Assembly Breakdown Cards
          ========================================================================= */}
      <div className="generation-stats-summary-grid">
        {/* Completed */}
        <div className="gen-stat-box done">
          <div className="gen-stat-number">{doneShotsCount} / {totalShots}</div>
          <div className="gen-stat-title">
            <CheckCircle2 size={13} style={{ color: "#34d399" }} />
            <span>Shots Completed</span>
          </div>
        </div>

        {/* Currently Generating */}
        <div className="gen-stat-box generating">
          <div className="gen-stat-number">{generatingShotsCount}</div>
          <div className="gen-stat-title">
            <div className="pulse-spinner" style={{ width: "12px", height: "12px", borderWidth: "2px" }} />
            <span>Active Synthesis</span>
          </div>
        </div>

        {/* Queued */}
        <div className="gen-stat-box queued">
          <div className="gen-stat-number">{queuedShotsCount}</div>
          <div className="gen-stat-title">
            <Clock size={13} style={{ color: "#f59e0b" }} />
            <span>Queued</span>
          </div>
        </div>

        {/* Failed / Retrying */}
        <div className={`gen-stat-box ${failedShotsCount > 0 ? "failed" : ""}`}>
          <div className="gen-stat-number">
            {failedShotsCount} {retryingShotsCount > 0 ? `(${retryingShotsCount} retrying)` : ""}
          </div>
          <div className="gen-stat-title">
            <AlertCircle size={13} style={{ color: failedShotsCount > 0 ? "#f87171" : "#64748b" }} />
            <span>Failed Shots</span>
          </div>
        </div>

        {/* Assembly Status Box */}
        <div className="gen-stat-box assembly">
          <div className="gen-stat-status-text">
            {isAssembled
              ? "✓ Master Assembled"
              : isAssembling
              ? "⚡ FFmpeg Rendering"
              : isAssemblyQueued
              ? "🕒 Assembly Queued"
              : isAssemblyFailed
              ? "✕ Assembly Failed"
              : allShotsDone
              ? "Ready to Assemble"
              : "Waiting for Clips"}
          </div>
          <div className="gen-stat-title">
            <Film size={13} style={{ color: "#38bdf8" }} />
            <span>Final Assembly</span>
          </div>
        </div>
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
                <option key={m.id} value={m.id} disabled={m.is_available === false}>
                  {m.name} ({m.provider_name}) {m.is_available === false ? "— Unavailable (Missing Key)" : ""}
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
                className={`model-pill-btn ${selectedModelId === m.id ? "active" : ""} ${m.is_available === false ? "disabled" : ""}`}
                onClick={() => {
                  if (m.is_available !== false) {
                    handleModelChange(m.id);
                  }
                }}
                disabled={switchingModel || m.is_available === false}
                title={m.is_available === false ? (m.unavailability_reason || "Model unavailable: API credentials not configured in environment") : m.description}
                style={{ opacity: m.is_available === false ? 0.5 : 1, cursor: m.is_available === false ? "not-allowed" : "pointer" }}
              >
                <Cpu size={14} style={{ color: selectedModelId === m.id ? "#c4b5fd" : "#94a3b8" }} />
                <span>{m.name}</span>
                {m.is_available === false ? (
                  <span style={{ fontSize: "0.65rem", padding: "0.1rem 0.35rem", borderRadius: "9999px", background: "rgba(239, 68, 68, 0.25)", color: "#fca5a5" }}>
                    Unavailable
                  </span>
                ) : m.is_default ? (
                  <span style={{ fontSize: "0.65rem", padding: "0.1rem 0.35rem", borderRadius: "9999px", background: "rgba(139, 92, 246, 0.3)", color: "#ffffff" }}>
                    Default
                  </span>
                ) : null}
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

          {selectedModel.is_available === false && (
            <div style={{ display: "flex", alignItems: "center", gap: "0.45rem", padding: "0.5rem 0.75rem", background: "rgba(239, 68, 68, 0.12)", border: "1px solid rgba(239, 68, 68, 0.3)", borderRadius: "6px", width: "100%", marginTop: "0.5rem", color: "#fca5a5", fontSize: "0.78rem" }}>
              <AlertCircle size={14} style={{ flexShrink: 0 }} />
              <span>{selectedModel.unavailability_reason || "This model is currently unavailable because required environment credentials (API key) are missing."}</span>
            </div>
          )}
        </div>
      </div>

      {/* Dual Progress Bars: Video Clips vs Full Pipeline */}
      <div className="dual-progress-container">
        {/* Video Generation Progress */}
        <div className="progress-subpanel">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.45rem" }}>
            <span style={{ fontSize: "0.82rem", fontWeight: 600, color: "#e2e8f0" }}>
              Video Clip Synthesis Progress
            </span>
            <span style={{ fontSize: "0.82rem", fontWeight: 700, color: "#38bdf8" }}>
              {doneShotsCount} of {totalShots} Clips ({videoProgressPercent}%)
            </span>
          </div>
          <div className="progress-bar-track">
            <div
              className="progress-bar-fill"
              style={{
                width: `${Math.max(4, videoProgressPercent)}%`,
                background: "linear-gradient(90deg, #0284c7 0%, #38bdf8 100%)",
              }}
            />
          </div>
        </div>

        {/* FFmpeg Video Assembly Status */}
        <div className="progress-subpanel">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.45rem" }}>
            <span style={{ fontSize: "0.82rem", fontWeight: 600, color: "#e2e8f0" }}>
              FFmpeg Multi-Track Assembly
            </span>
            <span
              style={{
                fontSize: "0.82rem",
                fontWeight: 700,
                color: isAssembled ? "#34d399" : isAssembling ? "#f59e0b" : "#94a3b8",
              }}
            >
              {isAssembled ? "100% (Assembled)" : isAssembling ? "Rendering Audio & Video..." : "Awaiting Clips"}
            </span>
          </div>
          <div className="progress-bar-track">
            <div
              className="progress-bar-fill"
              style={{
                width: isAssembled ? "100%" : isAssembling ? "75%" : isReadyToAssemble ? "30%" : "5%",
                background: isAssembled
                  ? "linear-gradient(90deg, #10b981 0%, #059669 100%)"
                  : "linear-gradient(90deg, #d97706 0%, #7c3aed 100%)",
              }}
            />
          </div>
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
            flexWrap: "wrap",
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

      {/* Final Assembled Video Banner if complete */}
      {isAssembled && project.final_video_path && (
        <div
          className="studio-panel"
          style={{
            marginTop: "1.5rem",
            padding: "1.25rem 1.75rem",
            background: "rgba(16, 185, 129, 0.08)",
            borderColor: "rgba(16, 185, 129, 0.3)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: "1rem",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "0.85rem" }}>
            <CheckCircle2 size={24} style={{ color: "#34d399" }} />
            <div>
              <div style={{ fontSize: "0.98rem", fontWeight: 700, color: "#f8fafc" }}>
                Final {project.target_duration}s Advertisement Assembled & Ready
              </div>
              <div style={{ fontSize: "0.78rem", color: "#94a3b8" }}>
                Multi-clip temporal stitching, audio ducking, and watermark overlays complete.
              </div>
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
            <a
              href={getArtifactUrl(project.final_video_path)}
              download={`advertisement_${project.id.slice(0, 8)}.mp4`}
              className="btn-secondary-studio"
              style={{ textDecoration: "none", padding: "0.6rem 1rem", fontSize: "0.85rem", gap: "0.4rem" }}
            >
              <Download size={14} />
              <span>Download Master MP4</span>
            </a>
            <button
              type="button"
              className="btn-primary-studio"
              onClick={onViewFinal}
              style={{ padding: "0.6rem 1.25rem", fontSize: "0.85rem" }}
            >
              <span>Open in Cinema Editor & Master ➔</span>
            </button>
          </div>
        </div>
      )}

      {/* =========================================================================
          Live SSE Production Events Console (Collapsible)
          ========================================================================= */}
      {liveEvents.length > 0 && (
        <div className="live-events-drawer">
          <button
            type="button"
            className="live-events-toggle-btn"
            onClick={() => setEventsDrawerOpen(!eventsDrawerOpen)}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <Terminal size={14} style={{ color: "#38bdf8" }} />
              <span style={{ fontWeight: 600, fontSize: "0.78rem" }}>
                Live Production Event Stream ({liveEvents.length} events logged)
              </span>
            </div>
            {eventsDrawerOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>

          {eventsDrawerOpen && (
            <div className="live-events-log-container">
              {liveEvents.map((evt, idx) => (
                <div key={idx} className="event-log-entry">
                  <span className="log-time">{new Date(evt.timestamp).toLocaleTimeString()}</span>
                  <span className="log-type">[{evt.event_type}]</span>
                  {evt.shot_number && <span className="log-shot">Shot #{evt.shot_number}</span>}
                  <span className={`log-status ${evt.status.toLowerCase()}`}>{evt.status}</span>
                  {evt.provider && <span className="log-provider">({evt.provider})</span>}
                  {evt.error && <span className="log-error">Error: {evt.error}</span>}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
