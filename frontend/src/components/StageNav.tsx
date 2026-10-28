import type { FC } from "react";

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
  const steps: { step: WizardStep; label: string }[] = [
    { step: 1, label: "1. Brief & Assets" },
    { step: 2, label: "2. Storyboard Review" },
    { step: 3, label: "3. Video Generation" },
    { step: 4, label: "4. Final Advertisement" },
  ];

  return (
    <nav className="step-nav">
      {steps.map(({ step, label }) => {
        const isActive = currentStep === step;
        const isCompleted = step < currentStep || (step < maxUnlockedStep && !isActive);
        const isClickable = step <= maxUnlockedStep;

        return (
          <div
            key={step}
            className={`step-item ${isActive ? "active" : ""} ${
              isCompleted ? "completed" : ""
            }`}
            onClick={() => isClickable && onSelectStep(step)}
            style={{ cursor: isClickable ? "pointer" : "not-allowed" }}
          >
            <div className="step-circle">{isCompleted ? "✓" : step}</div>
            <span className="step-label">{label}</span>
          </div>
        );
      })}
    </nav>
  );
};
