// 快速成片 (quick route) page: the Streamlit center column for active_page="quick"
// — route banner above a five-tab strip (文案/图片/视频/音频/字幕), then the shared
// bottom action bar. The script tab is quick-only; pro uses wizard/plan/series.
import { navigate } from "../../app/router";
import { RouteBanner, Tabs } from "./fields";
import {
  AudioPanel,
  GenerateBar,
  ImagePanel,
  ScriptPanel,
  SubtitlePanel,
  VideoPanel,
} from "./panels";

export function QuickPage() {
  return (
    <div className="route-page">
      <RouteBanner
        route="quick"
        introKey="Route Quick Intro"
        linkLabelKey="Route Quick To Plan"
        onJump={() => navigate("/pro")}
      />
      <Tabs
        items={[
          { key: "script", label: "Tab Script", content: <ScriptPanel /> },
          { key: "image", label: "Image Settings", content: <ImagePanel /> },
          { key: "video", label: "Tab Video", content: <VideoPanel /> },
          { key: "audio", label: "Tab Audio", content: <AudioPanel /> },
          { key: "subtitle", label: "Tab Subtitle", content: <SubtitlePanel /> },
        ]}
      />
      <GenerateBar />
    </div>
  );
}
