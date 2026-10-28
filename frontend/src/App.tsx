import { useState, useEffect } from "react";
import { ProjectDetail } from "./types";
import { useProjectSSE } from "./hooks/useProjectSSE";
import { getProject, listProjects } from "./api/client";
import { Sidebar } from "./components/Sidebar";
import { Header } from "./components/Header";
import { WizardStep } from "./components/StageNav";
import { BriefStep } from "./components/BriefStep";
import { StoryboardStep } from "./components/StoryboardStep";
import { GenerationStep } from "./components/GenerationStep";
import { VideoEditor } from "./components/Editor/VideoEditor";
import { RecentProjectsModal } from "./components/RecentProjectsModal";
import { AlertTriangle, X } from "lucide-react";

export default function App() {
  const [activeProject, setActiveProject] = useState<ProjectDetail | null>(null);
  const [currentStep, setCurrentStep] = useState<WizardStep>(1);
  const [maxUnlockedStep, setMaxUnlockedStep] = useState<WizardStep>(1);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [recentModalOpen, setRecentModalOpen] = useState(false);
  const [recentCount, setRecentCount] = useState(0);

  // Load project count for sidebar badge
  const refreshProjectsCount = () => {
    listProjects()
      .then((items) => setRecentCount(items.length))
      .catch((err) => console.warn("Could not list projects count:", err));
  };

  useEffect(() => {
    refreshProjectsCount();
  }, []);

  // Hook into live Server-Sent Events for the active project
  const { connected } = useProjectSSE(activeProject?.id || null, (updated) => {
    setActiveProject(updated);

    // Auto-unlock steps based on stage
    if (updated.shots && updated.shots.length > 0) {
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
    refreshProjectsCount();
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
    refreshProjectsCount();
  };

  const handleRestart = () => {
    setActiveProject(null);
    setCurrentStep(1);
    setMaxUnlockedStep(1);
    setErrorMessage(null);
  };

  const handleSelectProject = async (projectId: string) => {
    try {
      setErrorMessage(null);
      const project = await getProject(projectId);
      setActiveProject(project);

      // Determine step from loaded project stage
      let step: WizardStep = 1;
      let maxStep: WizardStep = 1;

      if (project.stage === "ASSEMBLED" || project.final_video_path) {
        step = 4;
        maxStep = 4;
      } else if (
        ["STORYBOARD_APPROVED", "VIDEOS", "NARRATION"].includes(project.stage)
      ) {
        step = 3;
        maxStep = 3;
      } else if (project.shots && project.shots.length > 0) {
        step = 2;
        maxStep = 2;
      }

      setCurrentStep(step);
      setMaxUnlockedStep(maxStep);
    } catch (err: any) {
      console.error("Failed to load project:", err);
      setErrorMessage(
        err.response?.data?.detail || err.message || "Failed to load project"
      );
    }
  };

  return (
    <div className="studio-shell">
      {/* Persistent Left Sidebar */}
      <Sidebar
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
        onNewProject={handleRestart}
        onOpenRecent={() => setRecentModalOpen(true)}
        recentCount={recentCount}
      />

      {/* Main Studio Area */}
      <div className="studio-main">
        {/* Top App Bar */}
        <Header
          projectName={activeProject?.product_name}
          stage={activeProject?.stage}
          liveConnected={connected && Boolean(activeProject)}
          currentStep={currentStep}
          maxUnlockedStep={maxUnlockedStep}
          onSelectStep={(s) => setCurrentStep(s)}
          onOpenRecent={() => setRecentModalOpen(true)}
        />

        {/* Central Creative Workspace */}
        <main className="studio-content">
          {errorMessage && (
            <div className="studio-alert-error">
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <AlertTriangle size={16} />
                <span>{errorMessage}</span>
              </div>
              <button
                onClick={() => setErrorMessage(null)}
                title="Dismiss error"
              >
                <X size={16} />
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
              onBackToBrief={() => setCurrentStep(1)}
              onError={setErrorMessage}
            />
          )}

          {currentStep === 3 && activeProject && (
            <GenerationStep
              project={activeProject}
              onAssembled={handleAssembled}
              onViewFinal={() => setCurrentStep(4)}
              onError={setErrorMessage}
            />
          )}

          {currentStep === 4 && activeProject && (
            <VideoEditor
              project={activeProject}
              onBackToProduction={() => setCurrentStep(3)}
              onError={setErrorMessage}
            />
          )}
        </main>
      </div>

      {/* Recent Projects Modal */}
      <RecentProjectsModal
        isOpen={recentModalOpen}
        onClose={() => setRecentModalOpen(false)}
        onSelectProject={handleSelectProject}
        currentProjectId={activeProject?.id}
      />
    </div>
  );
}
