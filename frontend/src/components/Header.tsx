import { type FC } from "react";
import { ProjectStage } from "../types";
import { StageNav, WizardStep } from "./StageNav";
import { Layers } from "lucide-react";

interface HeaderProps {
  projectName?: string;
  stage?: ProjectStage;
  liveConnected?: boolean;
  currentStep: WizardStep;
  maxUnlockedStep: WizardStep;
  onSelectStep: (step: WizardStep) => void;
  onOpenRecent: () => void;
}

export const Header: FC<HeaderProps> = ({
  projectName,
  stage,
  liveConnected,
  currentStep,
  maxUnlockedStep,
  onSelectStep,
  onOpenRecent,
}) => {
  const getStageBadgeClass = (s?: ProjectStage) => {
    switch (s) {
      case "ASSEMBLED":
        return "done";
      case "VIDEOS":
      case "NARRATION":
      case "SCRIPT":
        return "generating";
      case "FAILED":
        return "failed";
      default:
        return "pending";
    }
  };

  return (
    <header className="studio-topbar">
      {/* Left: Breadcrumbs & Campaign Name */}
      <div className="topbar-left">
        <div className="project-breadcrumbs">
          <span>Campaigns</span>
          <span>/</span>
          <span className="project-name-active">
            {projectName || "Untitled Ad Film"}
          </span>
        </div>

        {stage && (
          <span className={`status-pill ${getStageBadgeClass(stage)}`}>
            {stage}
          </span>
        )}
      </div>

      {/* Center: Workflow Stepper */}
      <div className="topbar-center">
        <StageNav
          currentStep={currentStep}
          maxUnlockedStep={maxUnlockedStep}
          onSelectStep={onSelectStep}
        />
      </div>

      {/* Right: Live Sync & Projects Switcher */}
      <div className="topbar-right">
        <div
          className={`live-sync-indicator ${
            liveConnected ? "connected" : "disconnected"
          }`}
          title={liveConnected ? "Connected to realtime updates" : "Connecting..."}
        >
          <span className="sync-dot" />
          <span>{liveConnected ? "Live Sync" : "Sync Idle"}</span>
        </div>

        <button
          className="btn-secondary-studio"
          style={{ padding: "0.35rem 0.65rem", fontSize: "0.78rem" }}
          onClick={onOpenRecent}
          title="Browse saved campaigns"
        >
          <Layers size={14} />
          <span>Projects</span>
        </button>
      </div>
    </header>
  );
};
