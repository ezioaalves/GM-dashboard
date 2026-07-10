interface PillSelectProps<T extends string> {
  options: readonly T[];
  value: T | null;
  onChange: (value: T) => void;
  /** Accent for the selected pill; defaults to azure. */
  tone?: "azure" | "teal" | "amber";
  labels?: Partial<Record<T, string>>;
}

export function PillSelect<T extends string>({
  options,
  value,
  onChange,
  tone = "azure",
  labels,
}: PillSelectProps<T>) {
  return (
    <div className="pill-select">
      {options.map((opt) => (
        <button
          key={opt}
          className={`pill-option${value === opt ? ` pill-option--active pill-option--${tone}` : ""}`}
          onClick={() => onChange(opt)}
          type="button"
        >
          {labels?.[opt] ?? opt}
        </button>
      ))}
    </div>
  );
}
