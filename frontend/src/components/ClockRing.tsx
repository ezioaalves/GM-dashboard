import type { Clock } from "../types/clock";

const KIND_COLOR: Record<Clock["kind"], { fill: string; text: string }> = {
  countdown: { fill: "var(--amber)", text: "var(--amber-bright)" },
  progress: { fill: "var(--teal)", text: "var(--teal-bright)" },
};

export function ClockRing({ clock, size = 64 }: { clock: Clock; size?: number }) {
  const { fill, text } = KIND_COLOR[clock.kind];
  const pct = clock.segments > 0 ? clock.filled / clock.segments : 0;
  const deg = Math.round(pct * 360);
  const inner = size - 18;

  return (
    <div className="clock-item">
      <div
        className="clock-ring"
        style={{
          width: size,
          height: size,
          background: `conic-gradient(${fill} 0deg ${deg}deg, var(--border-strong) ${deg}deg 360deg)`,
        }}
      >
        <div
          className="clock-ring-inner"
          style={{ width: inner, height: inner, color: text }}
        >
          {clock.filled}/{clock.segments}
        </div>
      </div>
      <span className="clock-item-name">{clock.name}</span>
    </div>
  );
}
