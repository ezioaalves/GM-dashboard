import React from "react";

const TAU = Math.PI * 2;

function wedgePath(cx, cy, r, startAngle, endAngle) {
  const x1 = cx + r * Math.sin(startAngle);
  const y1 = cy - r * Math.cos(startAngle);
  const x2 = cx + r * Math.sin(endAngle);
  const y2 = cy - r * Math.cos(endAngle);
  const large = endAngle - startAngle > Math.PI ? 1 : 0;
  return `M ${cx} ${cy} L ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2} Z`;
}

/**
 * Pure SVG segment ring for a clock. `filled` is the count of filled
 * segments regardless of kind — for countdown clocks the caller (ClocksPage /
 * ClockCard) is responsible for deciding what "filled" visually means; per
 * the clock-engine contract, countdown `filled` already tracks remaining
 * segments, so this component simply lights up `filled` of `segments`
 * wedges starting from index 0.
 */
export function ClockRing({ segments, filled, kind, size = 72 }) {
  const cx = size / 2, cy = size / 2, r = size / 2 - 3;
  const gap = segments > 1 ? 0.04 : 0; // radians of breathing room between wedges
  const shown = kind === "countdown" ? filled : filled; // countdown: filled = remaining
  const wedges = [];
  for (let i = 0; i < segments; i++) {
    const start = (i / segments) * TAU + gap / 2;
    const end = ((i + 1) / segments) * TAU - gap / 2;
    wedges.push(
      <path
        key={i}
        d={wedgePath(cx, cy, r, start, end)}
        className={`clock-wedge ${i < shown ? "clock-wedge--filled" : ""} clock-wedge--${kind}`}
      />
    );
  }
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img"
         aria-label={`${filled} of ${segments} segments`}>
      {wedges}
    </svg>
  );
}

export default ClockRing;
