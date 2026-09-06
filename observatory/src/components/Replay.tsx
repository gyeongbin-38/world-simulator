import { Icon } from "./Shared";

export function ReplayControls({
  tick,
  horizon,
  playing,
  busy,
  speed,
  onSeek,
  onPlay,
  onSpeed,
}: {
  tick: number;
  horizon: number;
  playing: boolean;
  busy: boolean;
  speed: number;
  onSeek: (tick: number) => void;
  onPlay: () => void;
  onSpeed: (speed: number) => void;
}) {
  return (
    <footer className="replay-dock" aria-label="Observation replay controls">
      <div className="replay-identity">
        <Icon name="action" size={20} />
        <div>
          <strong>Observation replay</strong>
          <span>
            {busy ? "Loading observation…" : "Read-only · recorded time"}
          </span>
        </div>
      </div>
      <div className="playback-buttons">
        <button
          className="icon-button"
          aria-label="Previous tick"
          disabled={tick <= 0}
          onClick={() => onSeek(tick - 1)}
        >
          <Icon name="back" size={17} />
        </button>
        <button
          className="play-button"
          aria-label={playing ? "Pause replay" : "Play replay"}
          onClick={onPlay}
        >
          <Icon name={playing ? "pause" : "play"} size={20} />
        </button>
        <button
          className="icon-button"
          aria-label="Next tick"
          disabled={tick >= horizon}
          onClick={() => onSeek(tick + 1)}
        >
          <Icon name="arrow" size={17} />
        </button>
      </div>
      <div className="replay-track">
        <input
          type="range"
          aria-label="Observation tick"
          min={0}
          max={horizon}
          value={tick}
          onChange={(e) => onSeek(Number(e.target.value))}
          style={{ backgroundSize: `${(tick / horizon) * 100}% 100%` }}
        />
        <div className="track-labels">
          <span>00</span>
          <span>05</span>
          <span>10</span>
          <span>15</span>
          <span>{horizon}</span>
        </div>
      </div>
      <div className="replay-jump">
        <label htmlFor="jump-tick">Tick</label>
        <input
          id="jump-tick"
          aria-label="Jump to tick"
          type="number"
          min={0}
          max={horizon}
          value={tick}
          onChange={(e) => {
            if (e.target.value !== "") onSeek(Number(e.target.value));
          }}
        />
        <span>/ {horizon}</span>
      </div>
      <select
        aria-label="Replay speed"
        className="speed-select"
        value={speed}
        onChange={(e) => onSpeed(Number(e.target.value))}
      >
        <option value="0.5">0.5×</option>
        <option value="1">1×</option>
        <option value="2">2×</option>
        <option value="4">4×</option>
      </select>
    </footer>
  );
}
