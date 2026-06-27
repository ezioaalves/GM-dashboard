import React, { useState, useRef, useEffect } from "react";

export default function CustomSelect({ value, onChange, options, placeholder }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    function handleClick(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const selected = options.find((o) => (o.value ?? o) === value);
  const label = selected ? (selected.label ?? selected) : (placeholder || "Select…");

  return (
    <div className="custom-select" ref={ref}>
      <button
        type="button"
        className={`custom-select-trigger ${open ? "open" : ""}`}
        onClick={() => setOpen((o) => !o)}
      >
        <span>{label}</span>
        <span className="custom-select-arrow">▾</span>
      </button>
      {open && (
        <ul className="custom-select-dropdown">
          {options.map((opt) => {
            const val = opt.value ?? opt;
            const lbl = opt.label ?? opt;
            return (
              <li
                key={val}
                className={`custom-select-option ${val === value ? "selected" : ""}`}
                onMouseDown={() => { onChange(val); setOpen(false); }}
              >
                {lbl}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
