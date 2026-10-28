import { useState, useCallback, useEffect } from "react";
import { TimelineData } from "../types";

export interface TimelineHistoryState {
  past: TimelineData[];
  present: TimelineData;
  future: TimelineData[];
}

export function useTimelineHistory(initialTimeline: TimelineData) {
  const [history, setHistory] = useState<TimelineHistoryState>({
    past: [],
    present: initialTimeline,
    future: [],
  });

  const [savedSnapshot, setSavedSnapshot] = useState<string>(
    JSON.stringify(initialTimeline)
  );

  // Synchronize when a new external timeline is loaded
  const resetTimeline = useCallback((newTimeline: TimelineData) => {
    setHistory({
      past: [],
      present: newTimeline,
      future: [],
    });
    setSavedSnapshot(JSON.stringify(newTimeline));
  }, []);

  const updateTimeline = useCallback(
    (updater: TimelineData | ((prev: TimelineData) => TimelineData)) => {
      setHistory((curr) => {
        const next =
          typeof updater === "function" ? updater(curr.present) : updater;

        // Don't push identical states
        if (JSON.stringify(curr.present) === JSON.stringify(next)) {
          return curr;
        }

        return {
          past: [...curr.past.slice(-25), curr.present], // Keep up to 25 history frames
          present: next,
          future: [],
        };
      });
    },
    []
  );

  const undo = useCallback(() => {
    setHistory((curr) => {
      if (curr.past.length === 0) return curr;
      const previous = curr.past[curr.past.length - 1]!;
      const newPast = curr.past.slice(0, curr.past.length - 1);

      return {
        past: newPast,
        present: previous,
        future: [curr.present, ...curr.future],
      };
    });
  }, []);

  const redo = useCallback(() => {
    setHistory((curr) => {
      if (curr.future.length === 0) return curr;
      const next = curr.future[0]!;
      const newFuture = curr.future.slice(1);

      return {
        past: [...curr.past, curr.present],
        present: next,
        future: newFuture,
      };
    });
  }, []);

  const markSaved = useCallback((snapshot?: TimelineData) => {
    setHistory((curr) => {
      const snap = snapshot || curr.present;
      setSavedSnapshot(JSON.stringify(snap));
      return curr;
    });
  }, []);

  const isDirty = JSON.stringify(history.present) !== savedSnapshot;
  const canUndo = history.past.length > 0;
  const canRedo = history.future.length > 0;

  // Keyboard shortcuts (Ctrl+Z for undo, Ctrl+Y or Ctrl+Shift+Z for redo)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't intercept if user is typing in an input/textarea
      const target = e.target as HTMLElement;
      if (
        target &&
        (target.tagName === "INPUT" || target.tagName === "TEXTAREA")
      ) {
        return;
      }

      if ((e.ctrlKey || e.metaKey) && e.key === "z") {
        if (e.shiftKey) {
          e.preventDefault();
          redo();
        } else {
          e.preventDefault();
          undo();
        }
      } else if ((e.ctrlKey || e.metaKey) && e.key === "y") {
        e.preventDefault();
        redo();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [undo, redo]);

  return {
    timeline: history.present,
    updateTimeline,
    resetTimeline,
    undo,
    redo,
    canUndo,
    canRedo,
    isDirty,
    markSaved,
  };
}
