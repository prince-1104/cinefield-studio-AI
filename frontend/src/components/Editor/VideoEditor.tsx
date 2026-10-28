import { useState, useEffect, useCallback, type FC } from "react";
import {
  ProjectDetail,
  TimelineClip,
  TimelineOverlay,
  TimelineAudio,
  TimelineCaption,
  TimelineEditSummary,
} from "../../types";
import {
  getTimeline,
  saveTimeline,
  getTimelineHistory,
  exportTimeline,
  getDownloadUrl,
} from "../../api/client";
import { useTimelineHistory } from "../../hooks/useTimelineHistory";
import { EditorTopBar } from "./EditorTopBar";
import { EditorMediaPanel } from "./EditorMediaPanel";
import { EditorMonitor } from "./EditorMonitor";
import { EditorInspector } from "./EditorInspector";
import { EditorTimeline } from "./EditorTimeline";

interface VideoEditorProps {
  project: ProjectDetail;
  onBackToProduction: () => void;
  onError: (msg: string) => void;
}

export const VideoEditor: FC<VideoEditorProps> = ({
  project,
  onBackToProduction,
  onError,
}) => {
  const [loading, setLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [currentVersion, setCurrentVersion] = useState<number>(1);
  const [historySummaries, setHistorySummaries] = useState<TimelineEditSummary[]>([]);
  const [currentTime, setCurrentTime] = useState<number>(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // Initialize timeline history hook with fallback empty structure
  const {
    timeline,
    updateTimeline,
    resetTimeline,
    undo,
    redo,
    canUndo,
    canRedo,
    isDirty,
    markSaved,
  } = useTimelineHistory({
    settings: {
      duration_target_seconds: project.target_duration || 15,
      aspect_ratio: (project.aspect_ratio as any) || "16:9",
      fps: 24,
      width: 1920,
      height: 1080,
    },
    video_clips: [],
    overlays: [],
    audio_tracks: [],
    captions: [],
  });

  // Load timeline data from backend on mount or when project ID changes
  const fetchTimeline = useCallback(async () => {
    try {
      setLoading(true);
      const res = await getTimeline(project.id);
      setCurrentVersion(res.version);
      resetTimeline(res.timeline_data);

      const hist = await getTimelineHistory(project.id);
      setHistorySummaries(hist);

      if (res.timeline_data.video_clips.length > 0 && res.timeline_data.video_clips[0]) {
        setSelectedId(res.timeline_data.video_clips[0].id);
      }
    } catch (err: any) {
      console.error("Failed to load timeline:", err);
      onError(err.response?.data?.detail || err.message || "Failed to load timeline composition");
    } finally {
      setLoading(false);
    }
  }, [project.id, resetTimeline, onError]);

  useEffect(() => {
    fetchTimeline();
  }, [fetchTimeline]);

  // Synchronize rendering state with project stage
  const isRendering = project.stage === "RENDERING" || isExporting;

  // Handle Save
  const handleSave = async () => {
    try {
      setIsSaving(true);
      const res = await saveTimeline(project.id, timeline);
      setCurrentVersion(res.version);
      markSaved(res.timeline_data);

      const hist = await getTimelineHistory(project.id);
      setHistorySummaries(hist);
    } catch (err: any) {
      console.error("Failed to save timeline:", err);
      onError(err.response?.data?.detail || err.message || "Failed to save timeline changes");
    } finally {
      setIsSaving(false);
    }
  };

  // Handle Export Video
  const handleExport = async () => {
    try {
      setIsExporting(true);
      // Auto-save unsaved changes first before queuing export
      let editToExportId: string | undefined;
      if (isDirty) {
        const saved = await saveTimeline(project.id, timeline);
        setCurrentVersion(saved.version);
        markSaved(saved.timeline_data);
        editToExportId = saved.id;
      }

      await exportTimeline(project.id, editToExportId);
      const hist = await getTimelineHistory(project.id);
      setHistorySummaries(hist);
    } catch (err: any) {
      console.error("Failed to export timeline:", err);
      onError(err.response?.data?.detail || err.message || "Failed to queue timeline export");
      setIsExporting(false);
    }
  };

  // Reordering clips in timeline
  const handleReorderClips = (fromIndex: number, toIndex: number) => {
    updateTimeline((curr) => {
      const clips = [...curr.video_clips];
      const [moved] = clips.splice(fromIndex, 1);
      if (moved) {
        clips.splice(toIndex, 0, moved);
      }

      // Re-index and recalculate timeline_start offsets
      let accumulated = 0;
      clips.forEach((c, idx) => {
        c.shot_number = idx + 1;
        c.timeline_start = round(accumulated, 2);
        accumulated += c.duration;
      });

      return {
        ...curr,
        video_clips: clips,
      };
    });
  };

  // Updating a video clip
  const handleUpdateClip = (updated: TimelineClip) => {
    updateTimeline((curr) => {
      const clips = curr.video_clips.map((c) => (c.id === updated.id ? updated : c));

      // Recalculate timeline_start positions
      let accumulated = 0;
      clips.forEach((c) => {
        c.timeline_start = round(accumulated, 2);
        accumulated += c.duration;
      });

      return {
        ...curr,
        video_clips: clips,
      };
    });
  };

  // Deleting a clip
  const handleDeleteClip = (clipId: string) => {
    if (timeline.video_clips.length <= 1) {
      onError("Timeline requires at least one video scene.");
      return;
    }
    updateTimeline((curr) => {
      const clips = curr.video_clips.filter((c) => c.id !== clipId);
      let accumulated = 0;
      clips.forEach((c, idx) => {
        c.shot_number = idx + 1;
        c.timeline_start = round(accumulated, 2);
        accumulated += c.duration;
      });

      return {
        ...curr,
        video_clips: clips,
      };
    });

    if (selectedId === clipId) {
      setSelectedId(timeline.video_clips[0]?.id || null);
    }
  };

  // Duplicating a clip
  const handleDuplicateClip = (clipId: string) => {
    updateTimeline((curr) => {
      const idx = curr.video_clips.findIndex((c) => c.id === clipId);
      if (idx === -1) return curr;

      const orig = curr.video_clips[idx];
      if (!orig) return curr;

      const dup: TimelineClip = {
        ...orig,
        id: crypto.randomUUID ? crypto.randomUUID() : String(Math.random()),
        shot_number: orig.shot_number + 1,
        source_path: orig.source_path,
        source_duration: orig.source_duration,
        source_start: orig.source_start,
        source_end: orig.source_end,
        timeline_start: orig.timeline_start,
        duration: orig.duration,
        volume: orig.volume,
        transition: orig.transition,
      };

      const clips = [...curr.video_clips];
      clips.splice(idx + 1, 0, dup);

      let accumulated = 0;
      clips.forEach((c, i) => {
        c.shot_number = i + 1;
        c.timeline_start = round(accumulated, 2);
        accumulated += c.duration;
      });

      return {
        ...curr,
        video_clips: clips,
      };
    });
  };

  // Moving a clip earlier or later
  const handleMoveClip = (clipId: string, direction: "earlier" | "later") => {
    const idx = timeline.video_clips.findIndex((c) => c.id === clipId);
    if (idx === -1) return;
    const targetIdx = direction === "earlier" ? idx - 1 : idx + 1;
    if (targetIdx >= 0 && targetIdx < timeline.video_clips.length) {
      handleReorderClips(idx, targetIdx);
    }
  };

  // Updating overlay, audio, or caption
  const handleUpdateOverlay = (updated: TimelineOverlay) => {
    updateTimeline((curr) => ({
      ...curr,
      overlays: curr.overlays.map((o) => (o.id === updated.id ? updated : o)),
    }));
  };

  const handleUpdateAudio = (updated: TimelineAudio) => {
    updateTimeline((curr) => ({
      ...curr,
      audio_tracks: curr.audio_tracks.map((a) => (a.id === updated.id ? updated : a)),
    }));
  };

  const handleUpdateCaption = (updated: TimelineCaption) => {
    updateTimeline((curr) => ({
      ...curr,
      captions: curr.captions.map((cap) => (cap.id === updated.id ? updated : cap)),
    }));
  };

  // Aspect ratio toggle
  const handleToggleAspect = () => {
    updateTimeline((curr) => {
      const nextAspect = curr.settings.aspect_ratio === "16:9" ? "9:16" : "16:9";
      return {
        ...curr,
        settings: {
          ...curr.settings,
          aspect_ratio: nextAspect,
          width: nextAspect === "9:16" ? 1080 : 1920,
          height: nextAspect === "9:16" ? 1920 : 1080,
        },
      };
    });
  };

  const selectedClip = timeline.video_clips.find((c) => c.id === selectedId);
  const selectedOverlay = timeline.overlays.find((o) => o.id === selectedId);
  const selectedAudio = timeline.audio_tracks.find((a) => a.id === selectedId);
  const selectedCaption = timeline.captions.find((cap) => cap.id === selectedId);

  const selectedClipIndex = selectedClip
    ? timeline.video_clips.findIndex((c) => c.id === selectedClip.id)
    : -1;

  const totalDuration = timeline.video_clips.reduce((sum, c) => sum + c.duration, 0) || 15;
  const downloadUrl = project.final_video_path ? getDownloadUrl(project.id) : null;
  const hasRenderedVideo = Boolean(project.final_video_path);

  if (loading) {
    return (
      <div className="editor-loading-screen">
        <div className="pulse-spinner" style={{ width: "32px", height: "32px" }} />
        <span>Loading Pexyl Studio Customization Workspace...</span>
      </div>
    );
  }

  return (
    <div className="video-editor-workspace">
      {/* Top Application Bar */}
      <EditorTopBar
        projectName={project.product_name}
        version={currentVersion}
        isDirty={isDirty}
        canUndo={canUndo}
        canRedo={canRedo}
        onUndo={undo}
        onRedo={redo}
        onSave={handleSave}
        onExport={handleExport}
        isSaving={isSaving}
        isExporting={isRendering}
        downloadUrl={downloadUrl}
        hasRenderedVideo={hasRenderedVideo}
        history={historySummaries}
        onSelectVersion={async (id) => {
          // Switch version
          const histItem = historySummaries.find((h) => h.id === id);
          if (histItem) {
            fetchTimeline();
          }
        }}
        onBackToProduction={onBackToProduction}
      />

      {/* Main 3-Column Studio Body */}
      <div className="editor-body-grid">
        {/* Left Column: Media & Project Assets */}
        <EditorMediaPanel
          videoClips={timeline.video_clips}
          audioTracks={timeline.audio_tracks}
          overlays={timeline.overlays}
          captions={timeline.captions}
          productImage={project.product_image_path}
          onSelectClip={(id) => setSelectedId(id)}
          selectedId={selectedId}
        />

        {/* Center Column: Video Program Monitor */}
        <EditorMonitor
          videoClips={timeline.video_clips}
          overlay={timeline.overlays[0]}
          captions={timeline.captions}
          currentTime={currentTime}
          totalDuration={totalDuration}
          aspectRatio={timeline.settings.aspect_ratio}
          onSeek={(t) => setCurrentTime(round(t, 2))}
          onToggleAspect={handleToggleAspect}
          renderedVideoUrl={project.final_video_path}
          isRendering={isRendering}
          renderingLabel={project.current_stage_label || undefined}
          renderProgress={project.progress_percent}
        />

        {/* Right Column: Contextual Inspector */}
        <EditorInspector
          selectedClip={selectedClip}
          selectedOverlay={selectedOverlay}
          selectedAudio={selectedAudio}
          selectedCaption={selectedCaption}
          onUpdateClip={handleUpdateClip}
          onUpdateOverlay={handleUpdateOverlay}
          onUpdateAudio={handleUpdateAudio}
          onUpdateCaption={handleUpdateCaption}
          onDeleteClip={handleDeleteClip}
          onDuplicateClip={handleDuplicateClip}
          onMoveClip={handleMoveClip}
          canMoveEarlier={selectedClipIndex > 0}
          canMoveLater={selectedClipIndex >= 0 && selectedClipIndex < timeline.video_clips.length - 1}
          canDeleteClip={timeline.video_clips.length > 1}
        />
      </div>

      {/* Bottom Row: Premiere Pro Multitrack Timeline */}
      <EditorTimeline
        videoClips={timeline.video_clips}
        overlays={timeline.overlays}
        audioTracks={timeline.audio_tracks}
        captions={timeline.captions}
        currentTime={currentTime}
        totalDuration={totalDuration}
        onSeek={(t) => setCurrentTime(round(t, 2))}
        selectedId={selectedId}
        onSelectItem={(id) => setSelectedId(id)}
        onReorderClips={handleReorderClips}
      />
    </div>
  );
};

function round(val: number, decimals: number = 2): number {
  const p = Math.pow(10, decimals);
  return Math.round(val * p) / p;
}
