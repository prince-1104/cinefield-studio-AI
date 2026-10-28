import { type FC } from "react";
import { Check, FileText, Sparkles, Video, Sliders } from "lucide-react";

export type WizardStep = 1 | 2 | 3 | 4;

interface StageNavProps {
  currentStep: WizardStep;
  maxUnlockedStep: WizardStep;
  onSelectStep: (step: WizardStep) => void;
}

export const StageNav: FC<StageNavProps> = ({
  currentStep,
  maxUnlockedStep,
  onSelectStep,
}) => {
  const steps: { step: WizardStep; label: string; icon: typeof FileText }[] = [
    { step: 1, label: "Brief & Assets", icon: FileText },
    { step: 2, label: "Storyboard Arc", icon: Sparkles },
    { step: 3, label: "Video Production", icon: Video },
    { step: 4, label: "Editor & Master", icon: Sliders },
  ];

  return (
    <div className="workflow-stepper">
      {steps.map(({ step, label, icon: Icon }) => {
        const isActive = currentStep === step;
        const isCompleted = step < currentStep || (step < maxUnlockedStep && !isActive);
        const isUnlocked = step <= maxUnlockedStep;

        return (
          <button
            key={step}
            className={`stepper-tab ${isActive ? "active" : ""} ${
              isCompleted ? "completed" : ""
            } ${isUnlocked ? "unlocked" : ""}`}
            onClick={() => isUnlocked && onSelectStep(step)}
            disabled={!isUnlocked}
            title={isUnlocked ? `Go to ${label}` : "Complete previous stages first"}
          >
            <span className="stepper-num">
              {isCompleted ? <Check size={11} strokeWidth={3} /> : <Icon size={11} />}
            </span>
            <span>{label}</span>
          </button>
        );
      })}
    </div>
  );
};
