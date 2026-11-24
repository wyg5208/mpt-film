import { describe, expect, it } from "vitest";
import {
  VIDEO_PARAM_FIELD_NAMES,
  assembleVideoParams,
  initial,
  useParams,
} from "./params";

describe("assembleVideoParams", () => {
  it("covers every VideoParams field name from the store", () => {
    // schema.py VideoParams declares 44 fields; script_plan is pipeline-internal
    // and excluded by design, so the assembler covers 43 (golden-payload pytest
    // asserts exact set parity against the schema).
    expect(VIDEO_PARAM_FIELD_NAMES.length).toBe(43);
    expect(new Set(VIDEO_PARAM_FIELD_NAMES)).toEqual(
      new Set(Object.keys(initial))
    );
    expect(VIDEO_PARAM_FIELD_NAMES).toContain("video_subject");
    expect(VIDEO_PARAM_FIELD_NAMES).toContain("rounded_subtitle_background");
    expect(VIDEO_PARAM_FIELD_NAMES).toContain("plan_scene_count");
    expect(VIDEO_PARAM_FIELD_NAMES).not.toContain("script_plan");
    expect(VIDEO_PARAM_FIELD_NAMES).not.toContain("set");
    expect(VIDEO_PARAM_FIELD_NAMES).not.toContain("reset");
  });

  it("drops null/undefined fields so pydantic defaults apply", () => {
    const body = assembleVideoParams(useParams.getInitialState?.() ?? {
      ...initial,
      set: (p) => p,
      reset: () => {},
    });
    for (const key of Object.keys(initial)) {
      const value = initial[key as keyof typeof initial];
      if (value === null) {
        expect(body).not.toHaveProperty(key);
      } else {
        expect(body[key]).toEqual(value);
      }
    }
    expect(body).not.toHaveProperty("video_terms");
    expect(body).not.toHaveProperty("video_seed");
    expect(body).not.toHaveProperty("custom_audio_file");
    expect(body).not.toHaveProperty("script_plan");
  });

  it("passes explicitly set values through unchanged", () => {
    const state = {
      ...initial,
      video_subject: "deep sea",
      video_terms: ["whale", "abyss"],
      video_seed: 42,
      video_materials: [
        { provider: "local", url: "changofilmmaterials/a.mp4", duration: 8 },
      ],
      custom_audio_file: "voice/ref-1.wav",
      plan_target_duration: 60,
      set: (p: object) => p,
      reset: () => {},
    };
    const body = assembleVideoParams(state);
    expect(body.video_subject).toBe("deep sea");
    expect(body.video_terms).toEqual(["whale", "abyss"]);
    expect(body.video_seed).toBe(42);
    expect(body.video_materials).toEqual([
      { provider: "local", url: "changofilmmaterials/a.mp4", duration: 8 },
    ]);
    expect(body.custom_audio_file).toBe("voice/ref-1.wav");
    expect(body.plan_target_duration).toBe(60);
  });

  it("never leaks store internals into the payload", () => {
    const body = assembleVideoParams({
      ...initial,
      set: (p) => p,
      reset: () => {},
    });
    expect(body).not.toHaveProperty("set");
    expect(body).not.toHaveProperty("reset");
  });
});
