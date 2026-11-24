// i18n runtime (migration Part 2 / Part 6): the product ships Chinese + English
// only. Packs are produced by scripts/sync-i18n.mjs from webui/i18n/{zh,en}.json
// (other locales were removed by request). zh is the default UI language; keys
// missing from zh fall back to the en pack, then to the key itself (English
// source text). Language choice persists in localStorage and re-renders the
// whole app (demo lesson: logs/drawers must re-render on language switch,
// hence context-based t()).
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import zhPack from "./zh.json";
import enPack from "./en.json";

// 仅保留中英两种语言（用户要求移除其余 12 个语种）。
export const LANGUAGES = ["zh", "en"] as const;
export type Lang = (typeof LANGUAGES)[number];

const LANG_KEY = "cf_lang";

const packs: Record<Lang, Record<string, string>> = {
  zh: zhPack as unknown as Record<string, string>,
  en: enPack as unknown as Record<string, string>,
};

function defaultLang(): Lang {
  const saved = localStorage.getItem(LANG_KEY) as Lang | null;
  return saved && LANGUAGES.includes(saved) ? saved : "zh";
}

type I18nState = {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: (key: string, params?: Record<string, string | number>) => string;
};

const I18nContext = createContext<I18nState | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(defaultLang);
  const [pack, setPack] = useState<Record<string, string>>(() => packs[defaultLang()]);

  useEffect(() => {
    setPack(packs[lang]);
  }, [lang]);

  const setLang = useCallback((next: Lang) => {
    localStorage.setItem(LANG_KEY, next);
    setLangState(next);
  }, []);

  const t = useCallback(
    (key: string, params?: Record<string, string | number>) => {
      // zh 缺失时先回退 en 包，再回退 key 本身（英文源文案）。
      let text = pack[key] ?? packs.en[key] ?? key;
      if (params) {
        for (const [k, v] of Object.entries(params)) {
          text = text.replaceAll(`{${k}}`, String(v));
        }
      }
      return text;
    },
    [pack]
  );

  return (
    <I18nContext.Provider value={{ lang, setLang, t }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useI18n(): I18nState {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n outside I18nProvider");
  return ctx;
}
