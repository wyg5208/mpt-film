// Catalog hooks backed by the read-only reference API (app/controllers/v1/
// catalogs.py + video.py), so the panels list the same voices/fonts/sources/BGM
// the Streamlit UI resolves server-side. Each returns ready-to-render options.
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";

// /voices -> {voices: string[]}; friendly label strips the provider prefix and
// the Female/Neural noise the Streamlit format_func removes.
export function useVoices() {
  const q = useQuery({
    queryKey: ["catalog", "voices"],
    queryFn: () => api.get<{ voices: string[] }>("/voices"),
    staleTime: 5 * 60_000,
  });
  const options = (q.data?.voices ?? []).map((v) => ({
    label: v
      .split(":")
      .slice(-1)[0]
      .replace("Female", "♀")
      .replace("Male", "♂")
      .replace("Neural", "")
      .trim(),
    value: v,
  }));
  return { options, isLoading: q.isLoading };
}

// /fonts -> {fonts: [{name, file}]}
export function useFonts() {
  const q = useQuery({
    queryKey: ["catalog", "fonts"],
    queryFn: () => api.get<{ fonts: { name: string; file: string }[] }>("/fonts"),
    staleTime: 5 * 60_000,
  });
  const options = (q.data?.fonts ?? []).map((f) => ({ label: f.name, value: f.file }));
  return { options, isLoading: q.isLoading };
}

// /video-sources -> {groups:[{group, providers, configured}]}; flattened to a
// grouped option list. "local" is always available (needs no remote config).
export function useVideoSources() {
  const q = useQuery({
    queryKey: ["catalog", "video-sources"],
    queryFn: () =>
      api.get<{
        groups: { group: string; providers: string[]; configured: string[] }[];
      }>("/video-sources"),
    staleTime: 60_000,
  });
  const groups = (q.data?.groups ?? []).map((g) => ({
    group: g.group,
    options: g.providers.map((p) => ({ label: p, value: p })),
  }));
  groups.push({ group: "local", options: [{ label: "local", value: "local" }] });
  return { groups, isLoading: q.isLoading };
}

// /musics -> {files:[{name, file}]} for the preset-song picker.
export function useBgmFiles() {
  const q = useQuery({
    queryKey: ["catalog", "musics"],
    queryFn: () => api.get<{ files: { name: string; file: string }[] }>("/musics"),
    staleTime: 5 * 60_000,
  });
  const options = (q.data?.files ?? []).map((f) => ({ label: f.name, value: f.file }));
  return { options, isLoading: q.isLoading };
}
