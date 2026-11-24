// Small presentational primitives shared by the four generation panels, so the
// React pages read like the Streamlit containers (bordered panel + labelled
// controls) without repeating markup. All labels go through i18n t().
import type { ReactNode } from "react";
import { useState } from "react";
import { useI18n } from "../../i18n";

export interface Opt {
  label: string;
  value: string | number;
}

export function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="panel" data-testid={`panel-${title}`}>
      <h3 className="panel-title">{title}</h3>
      <div className="panel-body">{children}</div>
    </section>
  );
}

export function Field({
  label,
  help,
  children,
}: {
  label: string;
  help?: string;
  children: ReactNode;
}) {
  const { t } = useI18n();
  return (
    <label className="field">
      <span className="field-label">
        {t(label)}
        {help ? <span className="field-help" title={t(help)}>ⓘ</span> : null}
      </span>
      {children}
    </label>
  );
}

export function Select({
  value,
  options,
  onChange,
  disabled,
}: {
  value: string | number;
  options: Opt[];
  onChange: (value: string) => void;
  disabled?: boolean;
}) {
  return (
    <select
      value={String(value)}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value)}
    >
      {options.map((o) => (
        <option key={String(o.value)} value={String(o.value)}>
          {o.label}
        </option>
      ))}
    </select>
  );
}

export function Slider({
  value,
  min,
  max,
  step = 1,
  suffix = "",
  onChange,
  disabled,
}: {
  value: number;
  min: number;
  max: number;
  step?: number;
  suffix?: string;
  onChange: (value: number) => void;
  disabled?: boolean;
}) {
  return (
    <div className="slider-row">
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(Number(e.target.value))}
      />
      <span className="slider-value">
        {value}
        {suffix}
      </span>
    </div>
  );
}

export function Checkbox({
  checked,
  onChange,
  label,
  disabled,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
  disabled?: boolean;
}) {
  const { t } = useI18n();
  return (
    <label className="check">
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
      />
      {t(label)}
    </label>
  );
}

// Segmented control: the Streamlit voice-mode / backend switch as a row of
// mutually-exclusive buttons.
export function Segmented({
  value,
  options,
  onChange,
}: {
  value: string;
  options: Opt[];
  onChange: (value: string) => void;
}) {
  const { t } = useI18n();
  return (
    <div className="segmented" role="tablist">
      {options.map((o) => (
        <button
          key={String(o.value)}
          type="button"
          role="tab"
          aria-selected={o.value === value}
          className={o.value === value ? "seg active" : "seg"}
          onClick={() => onChange(String(o.value))}
        >
          {t(o.label)}
        </button>
      ))}
    </div>
  );
}

// Tabs: the Streamlit st.tabs page navigation. Each tab is a labelled panel;
// all panels stay mounted (render-all parity) but only the active one shows,
// so params never drift when switching tabs. Accepts an optional controlled
// active/onActiveChange pair so sibling tabs can drive navigation (the pro
// route jumps from the wizard to the plan tab after generation).
export interface TabItem {
  key: string;
  label: string;
  content: ReactNode;
}

export function Tabs({
  items,
  defaultKey,
  active,
  onActiveChange,
}: {
  items: TabItem[];
  defaultKey?: string;
  active?: string;
  onActiveChange?: (key: string) => void;
}) {
  const { t } = useI18n();
  const [internal, setInternal] = useState(defaultKey ?? items[0]?.key ?? "");
  const current = items.find((i) => i.key === (active ?? internal)) ?? items[0];
  function select(key: string) {
    if (onActiveChange) onActiveChange(key);
    else setInternal(key);
  }
  return (
    <div className="tabs-wrap">
      <div className="tabs" role="tablist">
        {items.map((i) => (
          <button
            key={i.key}
            type="button"
            role="tab"
            aria-selected={i.key === current?.key}
            className={i.key === current?.key ? "tab active" : "tab"}
            onClick={() => select(i.key)}
          >
            {t(i.label)}
          </button>
        ))}
      </div>
      <div className="tab-panel" role="tabpanel">
        {items.map((i) => (
          <div key={i.key} hidden={i.key !== current?.key}>
            {i.content}
          </div>
        ))}
      </div>
    </div>
  );
}

// Route banner: the 快速成片 / 专业短剧 positioning strip above the tabs, with a
// badge, a one-line intro and a cross-route jump button (Main.py _render_route_banner).
export function RouteBanner({
  route,
  introKey,
  linkLabelKey,
  onJump,
}: {
  route: "quick" | "pro";
  introKey: string;
  linkLabelKey: string;
  onJump: () => void;
}) {
  const { t } = useI18n();
  const badgeKey = route === "quick" ? "Route Quick Badge" : "Route Pro Badge";
  return (
    <div className="route-banner">
      <div className="route-head">
        <span className="route-badge">{t(badgeKey)}</span>
        <button className="btn ghost route-jump" onClick={onJump}>
          {t(linkLabelKey)} →
        </button>
      </div>
      <p className="muted route-intro">{t(introKey)}</p>
    </div>
  );
}
