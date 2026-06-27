import React, { useState, useRef, useEffect } from "react";

export default function MultiTagSelect({ values, onChange, options, placeholder }) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    function handleClick(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const selected = new Set(values);

  const filtered = options.filter((opt) => {
    const val = opt.value ?? opt;
    const lbl = (opt.label ?? opt).toLowerCase();
    return !selected.has(val) && lbl.includes(query.toLowerCase());
  });

  function add(val) {
    if (!selected.has(val)) onChange([...values, val]);
    setQuery("");
    inputRef.current?.focus();
  }

  function remove(val) {
    onChange(values.filter((v) => v !== val));
  }

  function labelFor(val) {
    const opt = options.find((o) => (o.value ?? o) === val);
    return opt ? (opt.label ?? opt) : val;
  }

  return (
    <div className="multi-tag-select" ref={ref}>
      <div
        className="multi-tag-input-row"
        onClick={() => { setOpen(true); inputRef.current?.focus(); }}
      >
        {values.map((v) => (
          <span key={v} className="tag">
            {labelFor(v)}
            <button
              type="button"
              className="tag-remove"
              onMouseDown={(e) => { e.stopPropagation(); remove(v); }}
            >×</button>
          </span>
        ))}
        <input
          ref={inputRef}
          className="tag-input"
          value={query}
          placeholder={values.length === 0 ? (placeholder || "Search…") : ""}
          onFocus={() => setOpen(true)}
          onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
          onKeyDown={(e) => {
            if (e.key === "Backspace" && !query && values.length) {
              remove(values[values.length - 1]);
            }
          }}
        />
      </div>
      {open && filtered.length > 0 && (
        <ul className="custom-select-dropdown">
          {filtered.map((opt) => {
            const val = opt.value ?? opt;
            const lbl = opt.label ?? opt;
            return (
              <li
                key={val}
                className="custom-select-option"
                onMouseDown={() => add(val)}
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
