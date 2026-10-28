import { useState, useRef, type FC, type MouseEvent } from "react";
import {
  ZoomIn,
  ZoomOut,
  Film,
  Type,
  Sparkles,
  Mic,
  Music,
} from "lucide-react";
import {
  TimelineClip,
  TimelineOverlay,
  TimelineAudio,
  TimelineCaption,
} from "../../types";

interface EditorTimelineProps {
  videoClips: TimelineClip[];
  overlays: TimelineOverlay[];
  audioTracks: TimelineAudio[];
  captions: TimelineCaption[];
  currentTime: number;
  totalDuration: number;
  onSeek: (time: number) => void;
  selectedId: string | null;
  onSelectItem: (id: string) => void;
  onReorderClips: (fromIndex: number, toIndex: number) => void;
}

export const EditorTimeline: FC<EditorTimelineProps> = ({
  videoClips,
  overlays,
  audioTracks,
  captions,
  currentTime,
  totalDuration,
  onSeek,
  selectedId,
  onSelectItem,
  onReorderClips,
}) => {
  // Pixels per second for zoom scale (range: 12px/s to 80px/s)
  const [zoomScale, setZoomScale] = useState<number>(24);
  const [draggedClipIndex, setDraggedClipIndex] = useState<number | null>(null);
  const rulerRef = useRef<HTMLDivElement | null>(null);

  const narration = audioTracks.find((a) => a.track_type === "narration");
  const music = audioTracks.find((a) => a.track_type === "music");
  const logo = overlays.find((o) => o.asset_type === "logo");

  const timelinePixelWidth = Math.max(900, Math.ceil(totalDuration * zoomScale) + 120);

  // Handle clicking or dragging on the time ruler
  const handleRulerClick = (e: MouseEvent<HTMLDivElement>) => {
    if (!rulerRef.current) return;
    const rect = rulerRef.current.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const newTime = Math.max(0, Math.min(totalDuration, clickX / zoomScale));
    onSeek(newTime);
  };

  // Generate ruler tick marks
  const tickInterval = zoomScale > 40 ? 1 : zoomScale > 20 ? 5 : 10;
  const tickCount = Math.ceil(totalDuration / tickInterval) + 1;
  const ticks = Array.from({ length: tickCount }, (_, i) => i * tickInterval);

  // Drag and drop reordering handlers
  const handleDragStart = (idx: number) => {
    setDraggedClipIndex(idx);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDrop = (targetIdx: number) => {
    if (draggedClipIndex !== null && draggedClipIndex !== targetIdx) {
      onReorderClips(draggedClipIndex, targetIdx);
    }
    setDraggedClipIndex(null);
  };

  return (
    <div className="editor-timeline-panel">
      {/* Timeline Controls Toolbar */}
      <div className="timeline-toolbar">
        <div className="timeline-tracks-label">
          <span>TIMELINE</span>
          <span className="timeline-dur-badge">{totalDuration.toFixed(1)}s Total</span>
        </div>

        <div className="timeline-zoom-controls">
          <button
            className="editor-icon-btn"
            onClick={() => setZoomScale(Math.max(12, zoomScale - 6))}
            disabled={zoomScale <= 12}
            title="Zoom Out (-)"
          >
            <ZoomOut size={13} />
          </button>

          <span className="zoom-level-text">{Math.round((zoomScale / 24) * 100)}%</span>

          <button
            className="editor-icon-btn"
            onClick={() => setZoomScale(Math.min(80, zoomScale + 6))}
            disabled={zoomScale >= 80}
            title="Zoom In (+)"
          >
            <ZoomIn size={13} />
          </button>
        </div>
      </div>

      {/* Main Multitrack Area */}
      <div className="timeline-scroll-container">
        {/* Track Headers (Left fixed column) */}
        <div className="timeline-headers-column">
          <div className="track-header-spacer" />
          <div className="track-header-label">
            <Sparkles size={11} style={{ color: "#c084fc" }} />
            <span>V2 · Overlays</span>
          </div>
          <div className="track-header-label">
            <Type size={11} style={{ color: "#eab308" }} />
            <span>TXT · Captions</span>
          </div>
          <div className="track-header-label primary">
            <Film size={11} style={{ color: "#8b5cf6" }} />
            <span>V1 · Video</span>
          </div>
          <div className="track-header-label">
            <Mic size={11} style={{ color: "#38bdf8" }} />
            <span>A1 · Narration</span>
          </div>
          <div className="track-header-label">
            <Music size={11} style={{ color: "#a855f7" }} />
            <span>A2 · Music</span>
          </div>
        </div>

        {/* Tracks Content (Horizontally scrollable) */}
        <div className="timeline-tracks-viewport">
          <div
            className="timeline-tracks-content"
            style={{ width: `${timelinePixelWidth}px` }}
          >
            {/* Playhead Scrubber Line */}
            <div
              className="timeline-playhead"
              style={{ left: `${currentTime * zoomScale}px` }}
            >
              <div className="playhead-handle" />
              <div className="playhead-line" />
            </div>

            {/* Time Ruler */}
            <div
              ref={rulerRef}
              className="timeline-ruler"
              onClick={handleRulerClick}
            >
              {ticks.map((t) => (
                <div
                  key={t}
                  className="ruler-tick"
                  style={{ left: `${t * zoomScale}px` }}
                >
                  <span className="tick-label">{t}s</span>
                </div>
              ))}
            </div>

            {/* Track 1: Brand Logo Overlay (V2) */}
            <div className="timeline-track-lane overlay-lane">
              {logo && (
                <div
                  className={`timeline-block overlay-block ${selectedId === logo.id ? "selected" : ""}`}
                  style={{
                    left: `${logo.timeline_start * zoomScale}px`,
                    width: `${Math.max(40, (logo.timeline_end - logo.timeline_start) * zoomScale)}px`,
                  }}
                  onClick={() => onSelectItem(logo.id)}
                  title={`Brand Logo (${logo.position})`}
                >
                  <Sparkles size={11} />
                  <span className="block-title">Logo ({logo.position})</span>
                </div>
              )}
            </div>

            {/* Track 2: Captions Subtitles (TXT) */}
            <div className="timeline-track-lane captions-lane">
              {captions.map((cap) => {
                const dur = cap.timeline_end - cap.timeline_start;
                const width = Math.max(30, dur * zoomScale);
                return (
                  <div
                    key={cap.id}
                    className={`timeline-block caption-block ${selectedId === cap.id ? "selected" : ""}`}
                    style={{
                      left: `${cap.timeline_start * zoomScale}px`,
                      width: `${width}px`,
                    }}
                    onClick={() => onSelectItem(cap.id)}
                    title={`"${cap.text}" (${dur.toFixed(1)}s)`}
                  >
                    <Type size={11} />
                    <span className="block-title truncate">"{cap.text}"</span>
                  </div>
                );
              })}
            </div>

            {/* Track 3: Video Clips (V1) */}
            <div className="timeline-track-lane video-lane">
              {videoClips.map((clip, idx) => {
                const width = Math.max(48, clip.duration * zoomScale);
                const isSelected = selectedId === clip.id;
                const isDragging = draggedClipIndex === idx;

                return (
                  <div
                    key={clip.id}
                    draggable
                    onDragStart={() => handleDragStart(idx)}
                    onDragOver={handleDragOver}
                    onDrop={() => handleDrop(idx)}
                    className={`timeline-block video-block ${isSelected ? "selected" : ""} ${isDragging ? "dragging" : ""}`}
                    style={{
                      left: `${clip.timeline_start * zoomScale}px`,
                      width: `${width}px`,
                    }}
                    onClick={() => onSelectItem(clip.id)}
                  >
                    {/* Left Trim Handle */}
                    <div
                      className="trim-handle left"
                      title="Drag or edit in properties to trim in-point"
                    />

                    <div className="video-block-content">
                      <div className="video-block-header">
                        <span className="video-shot-num">Shot #{clip.shot_number}</span>
                        <span className="video-dur-tag">{clip.duration.toFixed(1)}s</span>
                      </div>
                      <div className="video-block-sub truncate">
                        {clip.description || clip.transition || "Scene"}
                      </div>
                    </div>

                    {/* Right Trim Handle */}
                    <div
                      className="trim-handle right"
                      title="Drag or edit in properties to trim out-point"
                    />
                  </div>
                );
              })}
            </div>

            {/* Track 4: Narration Audio (A1) */}
            <div className="timeline-track-lane narration-lane">
              {narration && (
                <div
                  className={`timeline-block narration-block ${selectedId === narration.id ? "selected" : ""}`}
                  style={{
                    left: `${narration.timeline_start * zoomScale}px`,
                    width: `${Math.max(50, narration.duration * zoomScale)}px`,
                  }}
                  onClick={() => onSelectItem(narration.id)}
                  title="Synchronized Voiceover Audio"
                >
                  <Mic size={11} />
                  <span className="block-title">OpenAI Voiceover ({narration.duration.toFixed(1)}s)</span>
                  <span className="audio-vol-pill">{Math.round(narration.volume * 100)}%</span>
                </div>
              )}
            </div>

            {/* Track 5: Music Audio (A2) */}
            <div className="timeline-track-lane music-lane">
              {music && (
                <div
                  className={`timeline-block music-block ${selectedId === music.id ? "selected" : ""}`}
                  style={{
                    left: `${music.timeline_start * zoomScale}px`,
                    width: `${Math.max(50, music.duration * zoomScale)}px`,
                  }}
                  onClick={() => onSelectItem(music.id)}
                  title="Background Soundtrack"
                >
                  <Music size={11} />
                  <span className="block-title">Soundtrack ({music.duration.toFixed(1)}s)</span>
                  <span className="audio-vol-pill">{Math.round(music.volume * 100)}%</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
