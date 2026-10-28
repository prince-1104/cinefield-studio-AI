import { useState, type FC } from "react";
import {
  Film,
  Mic,
  Music,
  Type,
  Sparkles,
  Layers,
} from "lucide-react";
import { TimelineClip, TimelineAudio, TimelineOverlay, TimelineCaption } from "../../types";
import { getArtifactUrl } from "../../api/client";

interface EditorMediaPanelProps {
  videoClips: TimelineClip[];
  audioTracks: TimelineAudio[];
  overlays: TimelineOverlay[];
  captions: TimelineCaption[];
  productImage?: string | null;
  onSelectClip: (clipId: string) => void;
  selectedId: string | null;
}

export const EditorMediaPanel: FC<EditorMediaPanelProps> = ({
  videoClips,
  audioTracks,
  overlays,
  captions,
  productImage,
  onSelectClip,
  selectedId,
}) => {
  const [activeTab, setActiveTab] = useState<"video" | "audio" | "brand" | "captions">("video");

  const narration = audioTracks.find((a) => a.track_type === "narration");
  const music = audioTracks.find((a) => a.track_type === "music");
  const logo = overlays.find((o) => o.asset_type === "logo");

  return (
    <div className="editor-media-panel">
      <div className="media-panel-header">
        <div className="media-panel-title">
          <Layers size={14} style={{ color: "#8b5cf6" }} />
          <span>Project Assets</span>
        </div>

        {/* Tab switchers */}
        <div className="media-panel-tabs">
          <button
            className={`media-tab ${activeTab === "video" ? "active" : ""}`}
            onClick={() => setActiveTab("video")}
            title="Video Clips"
          >
            <Film size={13} />
            <span>Clips ({videoClips.length})</span>
          </button>
          <button
            className={`media-tab ${activeTab === "audio" ? "active" : ""}`}
            onClick={() => setActiveTab("audio")}
            title="Audio Tracks"
          >
            <Mic size={13} />
            <span>Audio ({audioTracks.length})</span>
          </button>
          <button
            className={`media-tab ${activeTab === "brand" ? "active" : ""}`}
            onClick={() => setActiveTab("brand")}
            title="Brand Overlays"
          >
            <Sparkles size={13} />
            <span>Brand</span>
          </button>
          <button
            className={`media-tab ${activeTab === "captions" ? "active" : ""}`}
            onClick={() => setActiveTab("captions")}
            title="Captions"
          >
            <Type size={13} />
            <span>Text ({captions.length})</span>
          </button>
        </div>
      </div>

      <div className="media-panel-content">
        {/* Video Clips List */}
        {activeTab === "video" && (
          <div className="media-items-stack">
            {videoClips.map((clip) => {
              const isSelected = selectedId === clip.id;
              return (
                <div
                  key={clip.id}
                  className={`media-card-item ${isSelected ? "selected" : ""}`}
                  onClick={() => onSelectClip(clip.id)}
                >
                  <div className="media-thumb-wrap">
                    {clip.source_path ? (
                      <video
                        src={getArtifactUrl(clip.source_path)}
                        preload="metadata"
                        className="media-thumb-video"
                      />
                    ) : (
                      <div className="media-thumb-fallback">
                        <Film size={18} />
                      </div>
                    )}
                    <span className="media-thumb-badge">#{clip.shot_number}</span>
                    <span className="media-thumb-duration">{clip.duration.toFixed(1)}s</span>
                  </div>

                  <div className="media-item-info">
                    <div className="media-item-title">
                      <span>Shot {clip.shot_number}</span>
                      {clip.transition && (
                        <span className="media-transition-pill">{clip.transition}</span>
                      )}
                    </div>
                    <div className="media-item-sub">
                      {clip.description || clip.visual_prompt || "Synthesized video scene"}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Audio Tracks */}
        {activeTab === "audio" && (
          <div className="media-items-stack">
            {narration && (
              <div
                className={`media-card-item ${selectedId === narration.id ? "selected" : ""}`}
                onClick={() => onSelectClip(narration.id)}
              >
                <div className="media-audio-icon-box">
                  <Mic size={18} style={{ color: "#38bdf8" }} />
                </div>
                <div className="media-item-info">
                  <div className="media-item-title">
                    <span>Voiceover Narration</span>
                    <span className="media-audio-vol-badge">{Math.round(narration.volume * 100)}%</span>
                  </div>
                  <div className="media-item-sub">
                    OpenAI text-to-speech synchronized voiceover ({narration.duration.toFixed(1)}s)
                  </div>
                </div>
              </div>
            )}

            {music && (
              <div
                className={`media-card-item ${selectedId === music.id ? "selected" : ""}`}
                onClick={() => onSelectClip(music.id)}
              >
                <div className="media-audio-icon-box music">
                  <Music size={18} style={{ color: "#a855f7" }} />
                </div>
                <div className="media-item-info">
                  <div className="media-item-title">
                    <span>Background Soundtrack</span>
                    <span className="media-audio-vol-badge">{Math.round(music.volume * 100)}%</span>
                  </div>
                  <div className="media-item-sub">
                    Dynamic ducked music track ({music.duration.toFixed(1)}s)
                  </div>
                </div>
              </div>
            )}

            {!narration && !music && (
              <div className="media-empty-msg">No audio tracks configured in this production.</div>
            )}
          </div>
        )}

        {/* Brand & Overlays */}
        {activeTab === "brand" && (
          <div className="media-items-stack">
            {logo && (
              <div
                className={`media-card-item ${selectedId === logo.id ? "selected" : ""}`}
                onClick={() => onSelectClip(logo.id)}
              >
                <div className="media-thumb-wrap logo-checkerboard" style={{ width: "44px", height: "44px" }}>
                  <img
                    src={getArtifactUrl(logo.asset_path)}
                    alt="Logo watermark"
                    style={{ maxWidth: "34px", maxHeight: "34px", objectFit: "contain" }}
                  />
                </div>
                <div className="media-item-info">
                  <div className="media-item-title">
                    <span>Brand Logo Overlay</span>
                    <span className="media-transition-pill">{logo.position}</span>
                  </div>
                  <div className="media-item-sub">
                    Watermark opacity {Math.round(logo.opacity * 100)}% · scale {Math.round(logo.scale * 100)}%
                  </div>
                </div>
              </div>
            )}

            {productImage && (
              <div className="media-card-item">
                <div className="media-thumb-wrap" style={{ width: "44px", height: "44px" }}>
                  <img
                    src={getArtifactUrl(productImage)}
                    alt="Product reference"
                    style={{ width: "100%", height: "100%", objectFit: "cover" }}
                  />
                </div>
                <div className="media-item-info">
                  <div className="media-item-title">
                    <span>Product Reference</span>
                  </div>
                  <div className="media-item-sub">Multimodal conditioning reference</div>
                </div>
              </div>
            )}

            {!logo && !productImage && (
              <div className="media-empty-msg">No brand assets uploaded for this project.</div>
            )}
          </div>
        )}

        {/* Captions */}
        {activeTab === "captions" && (
          <div className="media-items-stack">
            {captions.map((cap) => (
              <div
                key={cap.id}
                className={`media-card-item ${selectedId === cap.id ? "selected" : ""}`}
                onClick={() => onSelectClip(cap.id)}
              >
                <div className="media-audio-icon-box" style={{ background: "rgba(234, 179, 8, 0.12)" }}>
                  <Type size={16} style={{ color: "#eab308" }} />
                </div>
                <div className="media-item-info">
                  <div className="media-item-title">
                    <span>{cap.timeline_start.toFixed(1)}s – {cap.timeline_end.toFixed(1)}s</span>
                    <span className="media-transition-pill">{cap.position}</span>
                  </div>
                  <div className="media-item-sub">"{cap.text}"</div>
                </div>
              </div>
            ))}
            {captions.length === 0 && (
              <div className="media-empty-msg">No captions configured.</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
