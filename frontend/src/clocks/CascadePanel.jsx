import React, { useMemo, useState } from "react";
import {
  AlertTriangle,
  ChevronDown,
  Edit2,
  GitBranch,
  Play,
  Plus,
  Trash2,
  X,
} from "lucide-react";
import CustomSelect from "../components/CustomSelect";
import {
  useCascadesQuery,
  useClocksQuery,
  useDeleteCascade,
  useFireCascade,
  useSaveCascade,
} from "../api/clocks";

const TRIGGER_KIND_OPTIONS = [
  { value: "manual", label: "GM-fired" },
  { value: "clock_event", label: "Clock event" },
];

const CLOCK_EVENT_OPTIONS = [
  { value: "ticked", label: "Ticked" },
  { value: "filled", label: "Filled" },
  { value: "emptied", label: "Emptied" },
];

const OP_OPTIONS = [
  { value: "gte", label: ">=" },
  { value: "gt", label: ">" },
  { value: "eq", label: "==" },
  { value: "lt", label: "<" },
  { value: "lte", label: "<=" },
];

const VALUE_KIND_OPTIONS = [
  { value: "number", label: "Number" },
  { value: "half", label: "Half" },
  { value: "full", label: "Full" },
];

const LIFECYCLE_OPTIONS = [
  { value: "active", label: "Active" },
  { value: "resolved", label: "Resolved" },
  { value: "abandoned", label: "Abandoned" },
];

const DEFAULT_EFFECT = { clock_id: "", delta: 1, reason_template: "{rule_title}: {trigger_note}" };
const DEFAULT_FORM = {
  name: "",
  title: "",
  description: "",
  trigger_kind: "manual",
  trigger_clock_id: "",
  trigger_event: "ticked",
  condition: {},
  effects: [{ ...DEFAULT_EFFECT }],
  enabled: true,
};

function slugify(value) {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function clockName(clockNameById, id) {
  return clockNameById.get(id) || id || "Clock";
}

function opLabel(op) {
  return OP_OPTIONS.find((o) => o.value === op)?.label || op;
}

function conditionSummary(condition, clockNameById) {
  if (!condition || Object.keys(condition).length === 0) return "always";
  if (condition.all) {
    return `all(${condition.all.map((c) => conditionSummary(c, clockNameById)).join(", ")})`;
  }
  if (condition.any) {
    return `any(${condition.any.map((c) => conditionSummary(c, clockNameById)).join(", ")})`;
  }
  if (condition.lifecycle) {
    return `${clockName(clockNameById, condition.clock)} lifecycle is ${condition.lifecycle}`;
  }
  return `${clockName(clockNameById, condition.clock)} ${opLabel(condition.op)} ${condition.value}`;
}

function effectSummary(effects, clockNameById) {
  if (!effects || effects.length === 0) return "No effects";
  return effects
    .map((effect) => `${effect.delta > 0 ? "+" : ""}${effect.delta} ${clockName(clockNameById, effect.clock_id)}`)
    .join(", ");
}

function triggerSummary(rule, clockNameById) {
  if (rule.trigger_kind === "manual") return "GM-fired";
  return `when ${clockName(clockNameById, rule.trigger_clock_id)} ${rule.trigger_event}`;
}

function modeFor(condition) {
  if (!condition || Object.keys(condition).length === 0) return "always";
  if (condition.all) return "all";
  if (condition.any) return "any";
  if (condition.lifecycle) return "lifecycle";
  return "compare";
}

function defaultLeaf(clocks) {
  return { clock: clocks[0]?.id || "", op: "gte", value: 1 };
}

function defaultLifecycle(clocks) {
  return { clock: clocks[0]?.id || "", lifecycle: "active" };
}

function setConditionMode(mode, clocks) {
  if (mode === "always") return {};
  if (mode === "all") return { all: [defaultLeaf(clocks)] };
  if (mode === "any") return { any: [defaultLeaf(clocks)] };
  if (mode === "lifecycle") return defaultLifecycle(clocks);
  return defaultLeaf(clocks);
}

function serializeForm(form, editingId) {
  const title = form.title.trim();
  const payload = {
    title,
    description: form.description.trim(),
    trigger_kind: form.trigger_kind,
    trigger_clock_id: form.trigger_kind === "clock_event" ? form.trigger_clock_id || null : null,
    trigger_event: form.trigger_kind === "clock_event" ? form.trigger_event : null,
    condition: form.condition || {},
    effects: form.effects.map((effect) => ({
      clock_id: effect.clock_id,
      delta: Number(effect.delta),
      reason_template: effect.reason_template || "",
    })),
    enabled: Boolean(form.enabled),
  };
  if (editingId) return { id: editingId, ...payload };
  return {
    name: slugify(form.name || title) || `cascade-${Date.now()}`,
    ...payload,
  };
}

function ruleToForm(rule) {
  return {
    name: rule.name,
    title: rule.title || rule.name,
    description: rule.description || "",
    trigger_kind: rule.trigger_kind,
    trigger_clock_id: rule.trigger_clock_id || "",
    trigger_event: rule.trigger_event || "ticked",
    condition: rule.condition || {},
    effects: rule.effects?.length ? rule.effects : [{ ...DEFAULT_EFFECT }],
    enabled: rule.enabled,
  };
}

function ConditionNode({ condition, onChange, clocks, onRemove, removable }) {
  const mode = modeFor(condition);
  const clockOptions = clocks.map((clock) => ({ value: clock.id, label: clock.name }));
  const valueKind =
    condition?.value === "half" || condition?.value === "full" ? condition.value : "number";
  const branches = mode === "all" ? condition.all : mode === "any" ? condition.any : [];

  function updateBranch(index, next) {
    const key = mode;
    onChange({ [key]: branches.map((branch, i) => (i === index ? next : branch)) });
  }

  function removeBranch(index) {
    const key = mode;
    const next = branches.filter((_, i) => i !== index);
    onChange(next.length ? { [key]: next } : {});
  }

  return (
    <div className="cascade-condition-node">
      <div className="cascade-condition-row">
        <CustomSelect
          value={mode}
          onChange={(nextMode) => onChange(setConditionMode(nextMode, clocks))}
          options={[
            { value: "always", label: "Always" },
            { value: "all", label: "All" },
            { value: "any", label: "Any" },
            { value: "compare", label: "Clock value" },
            { value: "lifecycle", label: "Lifecycle" },
          ]}
        />
        {removable && (
          <button type="button" onClick={onRemove} aria-label="Remove condition">
            <X size={14} />
          </button>
        )}
      </div>

      {mode === "compare" && (
        <div className="cascade-condition-grid">
          <CustomSelect
            value={condition.clock || ""}
            onChange={(clock) => onChange({ ...condition, clock })}
            options={clockOptions}
          />
          <CustomSelect
            value={condition.op || "gte"}
            onChange={(op) => onChange({ ...condition, op })}
            options={OP_OPTIONS}
          />
          <CustomSelect
            value={valueKind}
            onChange={(nextKind) =>
              onChange({ ...condition, value: nextKind === "number" ? 1 : nextKind })
            }
            options={VALUE_KIND_OPTIONS}
          />
          {valueKind === "number" && (
            <input
              type="number"
              value={Number.isInteger(condition.value) ? condition.value : 1}
              onChange={(e) => onChange({ ...condition, value: parseInt(e.target.value, 10) || 0 })}
            />
          )}
        </div>
      )}

      {mode === "lifecycle" && (
        <div className="cascade-condition-grid cascade-condition-grid--two">
          <CustomSelect
            value={condition.clock || ""}
            onChange={(clock) => onChange({ ...condition, clock })}
            options={clockOptions}
          />
          <CustomSelect
            value={condition.lifecycle || "active"}
            onChange={(lifecycle) => onChange({ ...condition, lifecycle })}
            options={LIFECYCLE_OPTIONS}
          />
        </div>
      )}

      {(mode === "all" || mode === "any") && (
        <div className="cascade-condition-branches">
          {branches.map((branch, index) => (
            <ConditionNode
              key={index}
              condition={branch}
              onChange={(next) => updateBranch(index, next)}
              clocks={clocks}
              removable
              onRemove={() => removeBranch(index)}
            />
          ))}
          <div className="cascade-inline-actions">
            <button type="button" onClick={() => onChange({ [mode]: [...branches, defaultLeaf(clocks)] })}>
              <Plus size={14} /> Row
            </button>
            <button type="button" onClick={() => onChange({ [mode]: [...branches, defaultLifecycle(clocks)] })}>
              <Plus size={14} /> Lifecycle
            </button>
            <button type="button" onClick={() => onChange({ [mode]: [...branches, { all: [defaultLeaf(clocks)] }] })}>
              <Plus size={14} /> Group
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function EffectsEditor({ effects, onChange, clocks }) {
  const clockOptions = clocks.map((clock) => ({ value: clock.id, label: clock.name }));

  function update(index, patch) {
    onChange(effects.map((effect, i) => (i === index ? { ...effect, ...patch } : effect)));
  }

  function remove(index) {
    const next = effects.filter((_, i) => i !== index);
    onChange(next.length ? next : [{ ...DEFAULT_EFFECT }]);
  }

  return (
    <div className="cascade-effects">
      {effects.map((effect, index) => (
        <div key={index} className="cascade-effect-row">
          <CustomSelect
            value={effect.clock_id}
            onChange={(clock_id) => update(index, { clock_id })}
            options={clockOptions}
          />
          <input
            type="number"
            value={effect.delta}
            onChange={(e) => update(index, { delta: parseInt(e.target.value, 10) || 0 })}
          />
          <input
            value={effect.reason_template}
            onChange={(e) => update(index, { reason_template: e.target.value })}
            placeholder="{rule_title}: {trigger_note}"
          />
          <button type="button" onClick={() => remove(index)} aria-label="Remove effect">
            <Trash2 size={14} />
          </button>
        </div>
      ))}
      <button type="button" onClick={() => onChange([...effects, { ...DEFAULT_EFFECT }])}>
        <Plus size={14} /> Add Effect
      </button>
    </div>
  );
}

function RuleEditor({ editingRule, form, setForm, clocks, onClose, onSave, pending, error }) {
  const clockOptions = clocks.map((clock) => ({ value: clock.id, label: clock.name }));
  const canSave =
    form.title.trim() &&
    (editingRule || form.name.trim() || slugify(form.title)) &&
    form.effects.every((effect) => effect.clock_id && Number(effect.delta) !== 0) &&
    (form.trigger_kind === "manual" || (form.trigger_clock_id && form.trigger_event));

  return (
    <div className="modalBackdrop">
      <section className="markdownModal cascade-modal">
        <header className="modalHeader">
          <div>
            <h2>{editingRule ? "Edit Cascade Rule" : "New Cascade Rule"}</h2>
            <p>Rules move clocks in audited chains. Manual rules always preview before firing.</p>
          </div>
          <div className="modalActions">
            <button onClick={onClose}>
              <X size={16} /> Close
            </button>
          </div>
        </header>

        <div className="cascade-editor-body">
          {error && <div className="notice bad">{error}</div>}
          <div className="formGrid">
            {!editingRule && (
              <label className="field">
                <span>Name</span>
                <input
                  value={form.name}
                  onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
                  placeholder="failed-patrol"
                />
              </label>
            )}
            <label className={`field${editingRule ? " spanAll" : ""}`}>
              <span>Title</span>
              <input
                value={form.title}
                onChange={(e) => setForm((prev) => ({ ...prev, title: e.target.value }))}
                placeholder="Failed Patrol"
              />
            </label>
            <label className="field spanAll">
              <span>Description</span>
              <textarea
                value={form.description}
                onChange={(e) => setForm((prev) => ({ ...prev, description: e.target.value }))}
                rows={2}
              />
            </label>
            <label className="field">
              <span>Trigger</span>
              <CustomSelect
                value={form.trigger_kind}
                onChange={(trigger_kind) => setForm((prev) => ({ ...prev, trigger_kind }))}
                options={TRIGGER_KIND_OPTIONS}
              />
            </label>
            {form.trigger_kind === "clock_event" && (
              <>
                <label className="field">
                  <span>Trigger Clock</span>
                  <CustomSelect
                    value={form.trigger_clock_id}
                    onChange={(trigger_clock_id) => setForm((prev) => ({ ...prev, trigger_clock_id }))}
                    options={clockOptions}
                  />
                </label>
                <label className="field">
                  <span>Event</span>
                  <CustomSelect
                    value={form.trigger_event}
                    onChange={(trigger_event) => setForm((prev) => ({ ...prev, trigger_event }))}
                    options={CLOCK_EVENT_OPTIONS}
                  />
                </label>
              </>
            )}
          </div>

          <section className="cascade-editor-section">
            <h3>Condition</h3>
            <ConditionNode
              condition={form.condition}
              onChange={(condition) => setForm((prev) => ({ ...prev, condition }))}
              clocks={clocks}
            />
          </section>

          <section className="cascade-editor-section">
            <h3>Effects</h3>
            <EffectsEditor
              effects={form.effects}
              onChange={(effects) => setForm((prev) => ({ ...prev, effects }))}
              clocks={clocks}
            />
          </section>

          <label className="cascade-checkbox">
            <input
              type="checkbox"
              checked={form.enabled}
              onChange={(e) => setForm((prev) => ({ ...prev, enabled: e.target.checked }))}
            />
            <span>Enabled</span>
          </label>

          <div className="modalActions">
            <button onClick={onClose}>Cancel</button>
            <button className="active" disabled={!canSave || pending} onClick={onSave}>
              {pending ? "Saving..." : "Save Rule"}
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}

function FirePreviewModal({ rule, result, clocksById, pending, onCancel, onConfirm }) {
  return (
    <div className="modalBackdrop">
      <section className="markdownModal cascade-modal">
        <header className="modalHeader">
          <div>
            <h2>Fire Preview</h2>
            <p>{rule.title || rule.name}</p>
          </div>
          <div className="modalActions">
            <button onClick={onCancel}>
              <X size={16} /> Close
            </button>
          </div>
        </header>
        <div className="cascade-editor-body">
          {result.applied.length === 0 && result.skipped.length === 0 && (
            <p className="clock-history-empty">This rule would not move any clocks.</p>
          )}
          {result.applied.length > 0 && (
            <section className="cascade-preview-section">
              <h3>Applied</h3>
              {result.applied.map((tick, index) => (
                <div key={`${tick.clock_id}-${index}`} className="cascade-preview-row">
                  <span style={{ paddingLeft: `${tick.hop_depth * 14}px` }}>
                    {clockName(clocksById, tick.clock_id)}
                  </span>
                  <span className={tick.delta >= 0 ? "clock-history-delta up" : "clock-history-delta down"}>
                    {tick.delta >= 0 ? `+${tick.delta}` : tick.delta}
                  </span>
                  <span>{tick.filled_after}/{result.clocks[tick.clock_id]?.segments || "?"}</span>
                  <span className="clock-history-reason">{tick.reason}</span>
                </div>
              ))}
            </section>
          )}
          {result.skipped.length > 0 && (
            <section className="cascade-preview-section">
              <h3>Skipped</h3>
              {result.skipped.map((skip, index) => (
                <div key={`${skip.clock_id}-${index}`} className="cascade-preview-row">
                  <span>{clockName(clocksById, skip.clock_id)}</span>
                  <span>{skip.delta > 0 ? `+${skip.delta}` : skip.delta}</span>
                  <span className="clock-history-reason">{skip.why}</span>
                </div>
              ))}
            </section>
          )}
          {result.guard_trips.length > 0 && (
            <section className="cascade-preview-section">
              <h3>Warnings</h3>
              {result.guard_trips.map((warning) => (
                <div key={warning} className="notice warn cascade-warning">
                  <AlertTriangle size={14} />
                  <span>{warning}</span>
                </div>
              ))}
            </section>
          )}
          <div className="modalActions">
            <button onClick={onCancel}>Cancel</button>
            <button className="active" disabled={pending} onClick={onConfirm}>
              {pending ? "Firing..." : "Confirm Fire"}
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}

export default function CascadePanel({ clocks = [], clockNameById, onStatus, onError }) {
  const { data: activeClocks = [] } = useClocksQuery({ lifecycle: "active" });
  const { data: rules = [], isLoading, error } = useCascadesQuery();
  const saveMutation = useSaveCascade();
  const deleteMutation = useDeleteCascade();
  const fireMutation = useFireCascade();
  const [editorOpen, setEditorOpen] = useState(false);
  const [editingRule, setEditingRule] = useState(null);
  const [form, setForm] = useState(DEFAULT_FORM);
  const [formError, setFormError] = useState("");
  const [preview, setPreview] = useState(null);

  const clockOptionsSource = activeClocks.length ? activeClocks : clocks;
  const clocksById = useMemo(() => {
    const map = new Map(clockNameById);
    for (const clock of clockOptionsSource) map.set(clock.id, clock.name);
    return map;
  }, [clockNameById, clockOptionsSource]);

  function openCreate() {
    setEditingRule(null);
    setForm({
      ...DEFAULT_FORM,
      trigger_clock_id: clockOptionsSource[0]?.id || "",
      effects: [{ ...DEFAULT_EFFECT, clock_id: clockOptionsSource[0]?.id || "" }],
    });
    setFormError("");
    setEditorOpen(true);
  }

  function openEdit(rule) {
    setEditingRule(rule);
    setForm(ruleToForm(rule));
    setFormError("");
    setEditorOpen(true);
  }

  async function saveRule() {
    setFormError("");
    onError("");
    try {
      const result = await saveMutation.mutateAsync(serializeForm(form, editingRule?.id));
      onStatus(`Cascade rule "${result.title || result.name}" saved.`);
      setEditorOpen(false);
      setEditingRule(null);
    } catch (e) {
      const message = e.message || String(e);
      setFormError(message);
      onError(message);
    }
  }

  async function toggleRule(rule) {
    onError("");
    try {
      await saveMutation.mutateAsync({ id: rule.id, enabled: !rule.enabled });
      onStatus(`Cascade rule "${rule.title || rule.name}" ${rule.enabled ? "disabled" : "enabled"}.`);
    } catch (e) {
      onError(e.message || String(e));
    }
  }

  async function deleteRule(rule) {
    if (!window.confirm(`Delete cascade rule "${rule.title || rule.name}"?`)) return;
    onError("");
    try {
      await deleteMutation.mutateAsync(rule.id);
      onStatus(`Cascade rule "${rule.title || rule.name}" deleted.`);
    } catch (e) {
      onError(e.message || String(e));
    }
  }

  async function previewFire(rule) {
    const trigger_note = window.prompt("Optional trigger note for this fire:") || "";
    onError("");
    try {
      const result = await fireMutation.mutateAsync({ id: rule.id, dry_run: true, trigger_note });
      setPreview({ rule, trigger_note, result });
    } catch (e) {
      onError(e.message || String(e));
    }
  }

  async function confirmFire() {
    if (!preview) return;
    onError("");
    try {
      const result = await fireMutation.mutateAsync({
        id: preview.rule.id,
        dry_run: false,
        trigger_note: preview.trigger_note,
      });
      onStatus(`Cascade fired: ${result.applied.length} clocks moved.`);
      setPreview(null);
    } catch (e) {
      onError(e.message || String(e));
    }
  }

  return (
    <section className="cascade-panel">
      <div className="cascade-panel-header">
        <div>
          <h2>Cascade Rules</h2>
          <p>Consequences that move clocks together with a dry-run preview.</p>
        </div>
        <button onClick={openCreate}>
          <Plus size={16} /> New Rule
        </button>
      </div>

      {error && <div className="notice bad">{error.message}</div>}
      {isLoading && <p className="clock-history-empty">Loading cascade rules...</p>}
      {!isLoading && rules.length === 0 && (
        <p className="clock-empty">
          <GitBranch size={14} /> No cascade rules yet.
        </p>
      )}

      <div className="cascade-rule-list">
        {rules.map((rule) => (
          <article key={rule.id} className={`cascade-rule-row${rule.enabled ? "" : " cascade-rule-row--disabled"}`}>
            <div className="cascade-rule-main">
              <div className="cascade-rule-title">
                <h3>{rule.title || rule.name}</h3>
                <span className={`badge badge--${rule.enabled ? "ok" : "warn"}`}>
                  {rule.enabled ? "enabled" : "disabled"}
                </span>
              </div>
              <p>{triggerSummary(rule, clocksById)}</p>
              <p>{conditionSummary(rule.condition, clocksById)}</p>
              <p>{effectSummary(rule.effects, clocksById)}</p>
            </div>
            <div className="cascade-rule-actions">
              <button onClick={() => toggleRule(rule)}>
                <ChevronDown size={14} /> {rule.enabled ? "Disable" : "Enable"}
              </button>
              <button onClick={() => openEdit(rule)}>
                <Edit2 size={14} /> Edit
              </button>
              {rule.trigger_kind === "manual" && (
                <button onClick={() => previewFire(rule)} disabled={!rule.enabled}>
                  <Play size={14} /> Fire
                </button>
              )}
              <button onClick={() => deleteRule(rule)}>
                <Trash2 size={14} /> Delete
              </button>
            </div>
          </article>
        ))}
      </div>

      {editorOpen && (
        <RuleEditor
          editingRule={editingRule}
          form={form}
          setForm={setForm}
          clocks={clockOptionsSource}
          onClose={() => setEditorOpen(false)}
          onSave={saveRule}
          pending={saveMutation.isPending}
          error={formError}
        />
      )}

      {preview && (
        <FirePreviewModal
          rule={preview.rule}
          result={preview.result}
          clocksById={clocksById}
          pending={fireMutation.isPending}
          onCancel={() => setPreview(null)}
          onConfirm={confirmFire}
        />
      )}
    </section>
  );
}
