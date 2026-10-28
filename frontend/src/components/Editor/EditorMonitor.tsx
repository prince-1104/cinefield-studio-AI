import { useState, useRef, useEffect, type FC } from "react";
import {
  Play,
  Pause,
  RotateCcw,
  SkipBack,
  SkipForward,
  Tv,
  Smartphone,
  Volume2,
  VolumeX,
} from "lucide-react";
import { TimelineClip, TimelineOverlay, TimelineCaption } from "../../types";
import { getArtifactUrl } from "../../api/client";

interface EditorMonitorProps {
  videoClips: TimelineClip[];
  overlay?: TimelineOverlay;
  captions: TimelineCaption[];
  currentTime: number;
  totalDuration: number;
  aspectRatio: "16:9" | "9:16";
  onSeek: (time: number) => void;
  onToggleAspect: () => void;
  renderedVideoUrl?: string | null;
  isRendering?: boolean;
  renderingLabel?: string;
  renderProgress?: number;
}

export const EditorMonitor: FC<EditorMonitorProps> = ({
  videoClips,
  overlay,
  captions,
  currentTime,
  totalDuration,
  aspectRatio,
  onSeek,
  onToggleAspect,
  renderedVideoUrl,
  isRendering,
  renderingLabel,
  renderProgress = 0,
}) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const videoRef = useRef<HTMLVideoElement | null>(null);

  // Identify current clip based on timeline time
  const currentClip = videoClips.find(
    (c) =>
      currentTime >= c.timeline_start &&
      currentTime <= c.timeline_start + c.duration
  ) || videoClips[0];

  // Calculate local source time offset within current clip
  const localClipOffset = currentClip
    ? Math.min(
        currentClip.source_end,
        currentClip.source_start + Math.max(0, currentTime - currentClip.timeline_start)
      )
    : 0;

  // Active overlay
  const activeOverlay =
    overlay &&
    currentTime >= overlay.timeline_start &&
    currentTime <= overlay.timeline_end
      ? overlay
      : null;

  // Active caption
  const activeCaption = captions.find(
    (cap) => currentTime >= cap.timeline_start && currentTime <= cap.timeline_end
  );

  // Synchronize native video element when not using rendered composite
  useEffect(() => {
    if (videoRef.current) {
      if (renderedVideoUrl) {
        // If rendered composite exists, sync directly to currentTime
        if (Math.abs(videoRef.current.currentTime - currentTime) > 0.3) {
          videoRef.current.currentTime = currentTime;
        }
      } else if (currentClip) {
        // Sync to sub-clip source offset
        if (Math.abs(videoRef.current.currentTime - localClipOffset) > 0.4) {
          videoRef.current.currentTime = localClipOffset;
        }
      }
    }
  }, [currentTime, currentClip, renderedVideoUrl]);

  // Handle Playback Interval
  useEffect(() => {
    let animId: number;
    let lastStamp = performance.now();

    const loop = (now: number) => {
      const dt = (now - lastStamp) / 1000;
      lastStamp = now;

      if (isPlaying) {
        onSeek(Math.min(totalDuration, currentTime + dt));
        if (currentTime >= totalDuration) {
          setIsPlaying(false);
          onSeek(0);
        }
      }
      if (isPlaying) {
        animId = requestAnimationFrame(loop);
      }
    };

    if (isPlaying) {
      lastStamp = performance.now();
      animId = requestAnimationFrame(loop);
      videoRef.current?.play().catch(() => {});
    } else {
      videoRef.current?.pause();
    }

    return () => cancelAnimationFrame(animId);
  }, [isPlaying, currentTime, totalDuration, onSeek]);

  const togglePlay = () => {
    if (currentTime >= totalDuration) {
      onSeek(0);
    }
    setIsPlaying(!isPlaying);
  };

  const formatTimecode = (sec: number) => {
    const mins = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    const ms = Math.floor((sec % 1) * 10);
    return `${String(mins).padStart(2, "0")}:${String(s).padStart(2, "0")}.${ms}`;
  };

  // Overlay position positioning styles
  const getOverlayPositionStyle = (pos: string) => {
    switch (pos) {
      case "top_left":
        return { top: "18px", left: "18px" };
      case "bottom_right":
        return { bottom: "18px", right: "18px" };
      case "bottom_left":
        return { bottom: "18px", left: "18px" };
      case "center":
        return { top: "50%", left: "50%", transform: "translate(-50%, -50%)" };
      default:
        return { top: "18px", right: "18px" };
    }
  };

  const isPortrait = aspectRatio === "9:16";
  const activeVideoSrc = renderedVideoUrl
    ? getArtifactUrl(renderedVideoUrl)
    : currentClip?.source_path
    ? getArtifactUrl(currentClip.source_path)
    : "";

  return (
    <div className="editor-monitor-panel">
      {/* Monitor Header */}
      <div className="monitor-header">
        <div className="monitor-title-badge">
          <span>PROGRAM MONITOR</span>
          <span className="monitor-fps-tag">24 FPS</span>
        </div>

        <div className="monitor-tools-row">
          <button
            className={`monitor-aspect-pill ${isPortrait ? "portrait" : "landscape"}`}
            onClick={onToggleAspect}
            title={`Switch to ${isPortrait ? "16:9 Cinema" : "9:16 Social"}`}
          >
            {isPortrait ? <Smartphone size={13} /> : <Tv size={13} />}
            <span>{isPortrait ? "9:16 Mobile" : "16:9 Cinema"}</span>
          </button>
        </div>
      </div>

      {/* Video Viewport Stage */}
      <div className="monitor-stage-wrap">
        <div
          className={`monitor-viewport ${isPortrait ? "portrait" : "landscape"}`}
          style={{
            aspectRatio: isPortrait ? "9 / 16" : "16 / 9",
          }}
        >
          {activeVideoSrc ? (
            <video
              ref={videoRef}
              src={activeVideoSrc}
              muted={isMuted}
              playsInline
              preload="auto"
              className="monitor-video-elem"
              onClick={togglePlay}
            />
          ) : (
            <div className="monitor-video-empty">
              <span>No video clips loaded in timeline</span>
            </div>
          )}

          {/* Live Watermark Overlay Preview */}
          {activeOverlay && (
            <div
              className="monitor-watermark-overlay"
              style={{
                position: "absolute",
                ...getOverlayPositionStyle(activeOverlay.position),
                opacity: activeOverlay.opacity,
                transform: `${getOverlayPositionStyle(activeOverlay.position).transform || ""} scale(${activeOverlay.scale})`,
                transformOrigin: "center",
                pointerEvents: "none",
                zIndex: 10,
              }}
            >
              <img
                src={getArtifactUrl(activeOverlay.asset_path)}
                alt="Brand overlay"
                style={{
                  maxHeight: isPortrait ? "42px" : "48px",
                  maxWidth: isPortrait ? "120px" : "160px",
                  objectFit: "contain",
                }}
              />
            </div>
          )}

          {/* Live Subtitle Caption Preview */}
          {activeCaption && (
            <div
              className={`monitor-caption-overlay pos-${activeCaption.position}`}
              style={{
                fontSize: `${isPortrait ? activeCaption.font_size * 0.8 : activeCaption.font_size}px`,
                color: activeCaption.font_color,
              }}
            >
              <span>{activeCaption.text}</span>
            </div>
          )}

          {/* Rendering Progress Overlay */}
          {isRendering && (
            <div className="monitor-rendering-scrim">
              <div className="pulse-spinner" style={{ width: "36px", height: "36px" }} />
              <div style={{ marginTop: "1rem", fontWeight: 700, fontSize: "1rem", color: "#ffffff" }}>
                {renderingLabel || "Rendering Final Master in FFmpeg..."}
              </div>
              <div style={{ fontSize: "0.82rem", color: "#94a3b8", marginTop: "0.25rem" }}>
                {renderProgress}% Complete · Compiling trimmed clips, ducked audio & overlays
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Scrub Bar & Transport Controls */}
      <div className="monitor-controls-strip">
        <div className="transport-timecode">
          <span className="current-tc">{formatTimecode(currentTime)}</span>
          <span className="tc-divider">/</span>
          <span className="total-tc">{formatTimecode(totalDuration)}</span>
        </div>

        <div className="transport-buttons">
          <button
            className="transport-btn"
            onClick={() => onSeek(Math.max(0, currentTime - 1.0))}
            title="Step Back 1s"
          >
            <SkipBack size={15} />
          </button>

          <button
            className="transport-btn play-main"
            onClick={togglePlay}
            title={isPlaying ? "Pause (Space)" : "Play (Space)"}
          >
            {isPlaying ? <Pause size={17} /> : <Play size={17} style={{ marginLeft: "2px" }} />}
          </button>

          <button
            className="transport-btn"
            onClick={() => onSeek(Math.min(totalDuration, currentTime + 1.0))}
            title="Step Forward 1s"
          >
            <SkipForward size={15} />
          </button>

          <button
            className="transport-btn"
            onClick={() => onSeek(0)}
            title="Jump to Start"
          >
            <RotateCcw size={14} />
          </button>
        </div>

        <div className="transport-audio-tools">
          <button
            className="transport-btn"
            onClick={() => setIsMuted(!isMuted)}
            title={isMuted ? "Unmute Preview" : "Mute Preview"}
          >
            {isMuted ? <VolumeX size={15} /> : <Volume2 size={15} />}
          </button>
        </div>
      </div>
    </div>
  );
};
