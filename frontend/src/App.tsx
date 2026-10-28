import { useState } from "react";
import { ProjectDetail } from "./types";
import { useProjectSSE } from "./hooks/useProjectSSE";
import { Header } from "./components/Header";
import { StageNav, WizardStep } from "./components/StageNav";
import { BriefStep } from "./components/BriefStep";
import { StoryboardStep } from "./components/StoryboardStep";
import { GenerationStep } from "./components/GenerationStep";
import { PreviewStep } from "./components/PreviewStep";

export default function App() {
  const [activeProject, setActiveProject] = useState<ProjectDetail | null>(null);
  const [currentStep, setCurrentStep] = useState<WizardStep>(1);
  const [maxUnlockedStep, setMaxUnlockedStep] = useState<WizardStep>(1);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Hook into live Server-Sent Events for the active project
  const { connected } = useProjectSSE(activeProject?.id || null, (updated) => {
    setActiveProject(updated);

    // Auto-unlock steps based on stage
    if (updated.shots && updated.shots.length === 3) {
      setMaxUnlockedStep((prev) => (Math.max(prev, 2) as WizardStep));
    }
    if (
      ["STORYBOARD_APPROVED", "VIDEOS", "NARRATION", "ASSEMBLED"].includes(
        updated.stage
      )
    ) {
      setMaxUnlockedStep((prev) => (Math.max(prev, 3) as WizardStep));
    }
    if (updated.stage === "ASSEMBLED" || updated.final_video_path) {
      setMaxUnlockedStep(4);
    }
  });

  const handleProjectCreated = (project: ProjectDetail) => {
    setActiveProject(project);
    setErrorMessage(null);
    setCurrentStep(2);
    setMaxUnlockedStep(2);
  };

  const handleStoryboardApproved = (project: ProjectDetail) => {
    setActiveProject(project);
    setErrorMessage(null);
    setCurrentStep(3);
    setMaxUnlockedStep(3);
  };

  const handleAssembled = (project: ProjectDetail) => {
    setActiveProject(project);
    setErrorMessage(null);
    setCurrentStep(4);
    setMaxUnlockedStep(4);
  };

  const handleRestart = () => {
    setActiveProject(null);
    setCurrentStep(1);
    setMaxUnlockedStep(1);
    setErrorMessage(null);
  };

  return (
    <div className="app-container">
      <Header
        stage={activeProject?.stage}
        liveConnected={connected && Boolean(activeProject)}
      />

      <StageNav
        currentStep={currentStep}
        maxUnlockedStep={maxUnlockedStep}
        onSelectStep={(s) => setCurrentStep(s)}
      />

      {errorMessage && (
        <div className="alert-error" style={{ display: "flex", justifyContent: "space-between" }}>
          <span>⚠️ {errorMessage}</span>
          <button
            onClick={() => setErrorMessage(null)}
            style={{
              background: "none",
              border: "none",
              color: "#fca5a5",
              cursor: "pointer",
              fontWeight: 700,
            }}
          >
            ✕
          </button>
        </div>
      )}

      {currentStep === 1 && (
        <BriefStep
          onProjectCreated={handleProjectCreated}
          onError={setErrorMessage}
        />
      )}

      {currentStep === 2 && activeProject && (
        <StoryboardStep
          project={activeProject}
          onApproved={handleStoryboardApproved}
          onError={setErrorMessage}
        />
      )}

      {currentStep === 3 && activeProject && (
        <GenerationStep
          project={activeProject}
          onAssembled={handleAssembled}
          onError={setErrorMessage}
        />
      )}

      {currentStep === 4 && activeProject && (
        <PreviewStep project={activeProject} onRestart={handleRestart} />
      )}
    </div>
  );
}
