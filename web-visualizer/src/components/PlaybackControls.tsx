type Props = {
  currentStep: number;
  totalSteps: number;
  isPlaying: boolean;
  speed: number;
  onPlayPause: () => void;
  onStepBack: () => void;
  onStepForward: () => void;
  onReset: () => void;
  onScrub: (step: number) => void;
  onSpeedChange: (speed: number) => void;
};

export function PlaybackControls({
  currentStep,
  totalSteps,
  isPlaying,
  speed,
  onPlayPause,
  onStepBack,
  onStepForward,
  onReset,
  onScrub,
  onSpeedChange,
}: Props) {
  const progress = totalSteps > 0 ? (currentStep / Math.max(1, totalSteps - 1)) * 100 : 0;

  return (
    <div className="playback-controls">
      <div className="playback-buttons">
        <button
          onClick={onReset}
          title="Reset to beginning"
          aria-label="Reset"
          className="btn btn-icon"
        >
          ⏮
        </button>
        <button
          onClick={onStepBack}
          disabled={currentStep <= 0}
          title="Step back"
          aria-label="Step back"
          className="btn btn-icon"
        >
          ◀
        </button>
        <button
          onClick={onPlayPause}
          disabled={totalSteps === 0}
          title={isPlaying ? "Pause" : "Play"}
          aria-label={isPlaying ? "Pause" : "Play"}
          className="btn btn-icon btn-primary"
        >
          {isPlaying ? "⏸" : "▶"}
        </button>
        <button
          onClick={onStepForward}
          disabled={currentStep >= totalSteps - 1}
          title="Step forward"
          aria-label="Step forward"
          className="btn btn-icon"
        >
          ▶
        </button>
      </div>

      <div className="playback-scrub">
        <input
          type="range"
          min={0}
          max={Math.max(0, totalSteps - 1)}
          value={currentStep}
          onChange={(e) => onScrub(Number(e.target.value))}
          disabled={totalSteps === 0}
          aria-label="Scrub timeline"
          className="scrubber"
          style={{ background: `linear-gradient(to right, #d97706 ${progress}%, rgba(255,255,255,0.1) ${progress}%)` }}
        />
        <div className="playback-info">
          <span>
            step <strong>{currentStep + (totalSteps > 0 ? 1 : 0)}</strong> / {totalSteps}
          </span>
        </div>
      </div>

      <div className="playback-speed">
        <label htmlFor="speed-select" className="speed-label">speed</label>
        <select
          id="speed-select"
          value={speed}
          onChange={(e) => onSpeedChange(Number(e.target.value))}
          className="speed-select"
        >
          <option value={2000}>0.5×</option>
          <option value={1000}>1×</option>
          <option value={500}>2×</option>
          <option value={200}>5×</option>
          <option value={50}>20×</option>
        </select>
      </div>
    </div>
  );
}
