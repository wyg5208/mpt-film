// Small shared widgets for the settings/config parity pages: Streamlit-style
// expander cards, chip multi-selects, {placeholder} template formatting and
// download helpers.
import { useRef, useState, type ReactNode } from "react";
import { useI18n } from "../i18n";

// Format a Streamlit-style "{placeholder}" template from the i18n packs.
export function fmt(
  template: string,
  params: Record<string, string | number>
): string {
  return template.replace(/\{(\w+)\}/g, (whole, key: string) =>
    key in params ? String(params[key]) : whole
  );
}

// Same human size buckets as Main.py _format_file_size.
export function formatSize(bytes: number): string {
  if (bytes >= 1073741824) return `${(bytes / 1073741824).toFixed(2)} GB`;
  if (bytes >= 1048576) return `${(bytes / 1048576).toFixed(2)} MB`;
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(2)} KB`;
  return `${bytes} B`;
}

export function truncate(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max)}…` : text;
}

export function downloadJson(filename: string, payload: unknown): void {
  const blob = new Blob([JSON.stringify(payload, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// Expander card with the provider status badge in the header, mirroring
// Main.py `_render_provider_settings_expander`.
export function Expander({
  title,
  ready,
  children,
  defaultOpen = false,
}: {
  title: ReactNode;
  ready?: boolean;
  children: ReactNode;
  defaultOpen?: boolean;
}) {
  const { t } = useI18n();
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="expander">
      <button
        type="button"
        className="expander-head"
        onClick={() => setOpen((v) => !v)}
      >
        <span className="expander-title">{title}</span>
        {ready !== undefined && (
          <span className={ready ? "badge ok" : "badge"}>
            {ready
              ? t("Provider Configured Badge")
              : t("Provider Not Configured Badge")}
          </span>
        )}
        <span className="expander-caret">{open ? "▾" : "▸"}</span>
      </button>
      {open && <div className="expander-body">{children}</div>}
    </div>
  );
}

// Chip-based multi-select standing in for st.multiselect (publish platforms).
export function ChipMultiSelect({
  options,
  value,
  onChange,
}: {
  options: { value: string; label: string }[];
  value: string[];
  onChange: (next: string[]) => void;
}) {
  function toggle(option: string) {
    onChange(
      value.includes(option)
        ? value.filter((v) => v !== option)
        : [...value, option]
    );
  }
  return (
    <div className="chips">
      {options.map(({ value: v, label }) => (
        <button
          key={v}
          type="button"
          className={value.includes(v) ? "chip on" : "chip"}
          onClick={() => toggle(v)}
        >
          {value.includes(v) ? "✓ " : ""}
          {label}
        </button>
      ))}
    </div>
  );
}

// Hidden-file-input + trigger button pair used by key/preset importers.
export function FilePickButton({
  label,
  accept,
  onPick,
  className,
}: {
  label: string;
  accept: string;
  onPick: (file: File) => void;
  className?: string;
}) {
  const ref = useRef<HTMLInputElement>(null);
  return (
    <>
      <button
        type="button"
        className={className ?? "btn"}
        onClick={() => ref.current?.click()}
      >
        {label}
      </button>
      <input
        ref={ref}
        type="file"
        accept={accept}
        hidden
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onPick(file);
          e.target.value = "";
        }}
      />
    </>
  );
}
