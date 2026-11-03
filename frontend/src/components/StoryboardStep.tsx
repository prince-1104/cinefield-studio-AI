import { useState, useEffect, type FC } from "react";
import { ProjectDetail, VideoModelInfo } from "../types";
import { ShotCard } from "./ShotCard";
import { approveStoryboard, getVideoModels, selectProjectModel } from "../api/client";
import {
  Clapperboard,
  ArrowLeft,
  CheckCircle,
  Film,
  Clock,
  Cpu,
} from "lucide-react";

interface StoryboardStepProps {
  project: ProjectDetail;
  onApproved: (project: ProjectDetail) => void;
  onBackToBrief: () => void;
  onError: (msg: string) => void;
}

export const StoryboardStep: FC<StoryboardStepProps> = ({
  project,
  onApproved,
  onBackToBrief,
  onError,
}) => {
  const [approving, setApproving] = useState(false);
  const [models, setModels] = useState<VideoModelInfo[]>([]);
  const [selectedModelId, setSelectedModelId] = useState<string>(
    project.selected_video_model || ""
  );

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
      .catch((err) => console.warn("Failed to load video models in storyboard review:", err));
  }, [project.selected_video_model]);

  const shotCount = project.shots ? project.shots.length : 0;
  const hasShots = shotCount > 0;
  const targetDur = project.target_duration || 60;

  const handleModelSelect = async (newModelId: string) => {
    setSelectedModelId(newModelId);
    try {
      const found = models.find((m) => m.id === newModelId);
      await selectProjectModel(project.id, newModelId, found?.provider);
    } catch (err) {
      console.warn("Failed to persist model selection:", err);
    }
  };

  const handleApprove = async () => {
    setApproving(true);
    try {
      const found = models.find((m) => m.id === selectedModelId);
      await approveStoryboard(project.id, selectedModelId, found?.provider);
      onApproved(project);
    } catch (err: any) {
      console.error("Failed to approve storyboard:", err);
      onError(
        err.response?.data?.detail || err.message || "Failed to approve storyboard"
      );
    } finally {
      setApproving(false);
    }
  };

  return (
    <div className="storyboard-workspace">
      {/* Workspace Heading */}
      <div className="workspace-header">
        <div className="workspace-title-row">
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <h1 className="workspace-heading">Storyboard & Timeline Review</h1>
            <span className="status-pill pending" style={{ fontSize: "0.75rem" }}>
              <Clock size={12} />
              <span>{targetDur}s Planned · {shotCount} Shots</span>
            </span>
          </div>

          <button
            type="button"
            className="btn-secondary-studio"
            onClick={onBackToBrief}
            style={{ fontSize: "0.8rem", padding: "0.45rem 0.85rem" }}
          >
            <ArrowLeft size={14} />
            <span>Edit Campaign Brief</span>
          </button>
        </div>
        <p className="workspace-subheading">
          Review the generated {shotCount}-shot narrative sequence for <strong>{project.product_name}</strong>.
          Select your generative video model below to synthesize clips upon approval.
        </p>
      </div>

      {/* Script Narrative Arc Banner */}
      {project.script && (
        <div className="storyboard-narrative-card">
          <div className="narrative-icon-col">
            <Film size={18} />
          </div>
          <div className="narrative-content-col">
            <div className="narrative-label">Cohesive Script Narrative Arc</div>
            <p className="narrative-script-text">{project.script}</p>
          </div>
        </div>
      )}

      {/* Shots Grid or Waiting State */}
      {!hasShots ? (
        <div
          style={{
            textAlign: "center",
            padding: "4rem 2rem",
            backgroundColor: "var(--bg-surface)",
            borderRadius: "var(--radius-lg)",
            border: "1px dashed var(--border-default)",
          }}
        >
          <div className="pulse-spinner" style={{ margin: "0 auto 1.25rem auto" }} />
          <h3 style={{ fontSize: "1.1rem", fontWeight: 600, marginBottom: "0.5rem" }}>
            Architecting {targetDur}s Cinematic Arc...
          </h3>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", maxWidth: "520px", margin: "0 auto" }}>
            Structuring scenes, camera movements, timeline windows, and narration lines tailored to your campaign brief.
            This screen updates automatically via live stream.
          </p>
        </div>
      ) : (
        <>
          <div className="shots-filmstrip-grid">
            {project.shots.map((shot) => (
              <ShotCard key={shot.id} shot={shot} />
            ))}
          </div>

          {/* Action Bar with Model Selector */}
          <div
            className="studio-panel"
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "1.25rem 1.75rem",
              flexWrap: "wrap",
              gap: "1rem",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "1rem", flexWrap: "wrap" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "var(--status-done)", fontSize: "0.85rem" }}>
                <CheckCircle size={16} />
                <span>
                  {shotCount} shots covering {targetDur}.0s timeline validated
                </span>
              </div>

              {/* Model Selector dropdown in Action Bar */}
              <div style={{ display: "flex", alignItems: "center", gap: "0.45rem" }}>
                <Cpu size={14} style={{ color: "#8b5cf6" }} />
                <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)", fontWeight: 600 }}>
                  Synthesis Engine:
                </span>
                <select
                  value={selectedModelId}
                  onChange={(e) => handleModelSelect(e.target.value)}
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

            <div style={{ display: "flex", gap: "0.75rem" }}>
              <button
                type="button"
                className="btn-secondary-studio"
                onClick={onBackToBrief}
              >
                Modify Parameters
              </button>
              <button
                type="button"
                className="btn-primary-studio"
                onClick={handleApprove}
                disabled={approving}
              >
                {approving ? (
                  <>
                    <div className="pulse-spinner" style={{ width: "16px", height: "16px", borderWidth: "2px" }} />
                    <span>Queuing Synthesis Jobs...</span>
                  </>
                ) : (
                  <>
                    <Clapperboard size={16} />
                    <span>Approve Storyboard & Generate Video</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
};
