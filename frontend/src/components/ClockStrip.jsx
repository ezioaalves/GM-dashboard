import React from "react";
import { ClockRing } from "../clocks/ClockRing";
import { useClocksQuery } from "../api/clocks";

export function ClockStrip({ onOpenClocks }) {
  const { data: clocks } = useClocksQuery({ lifecycle: "active" });
  if (!clocks || clocks.length === 0) return null;

  return (
    <section className="clock-strip">
      {clocks.map((clock) => {
        const terminal =
          clock.kind === "countdown" ? clock.filled === 0 : clock.filled === clock.segments;
        const stale =
          clock.freshness_state === "stale_mirror" ||
          clock.mirror?.state === "failed" ||
          clock.mirror?.state === "missing_mirror";
        return (
          <button
            key={clock.id}
            className={`clock-strip-item${terminal ? " clock-strip-item--terminal" : ""}${
              stale ? " clock-strip-item--stale" : ""
            }`}
            onClick={onOpenClocks}
            title={clock.name}
          >
            <ClockRing segments={clock.segments} filled={clock.filled} kind={clock.kind} size={34} />
            <span className="clock-strip-name">{clock.name}</span>
            <span className="clock-strip-count">
              {clock.kind === "countdown" ? `${clock.filled} left` : `${clock.filled}/${clock.segments}`}
            </span>
          </button>
        );
      })}
    </section>
  );
}

export default ClockStrip;
