// 专业短剧 (pro route) page: the Streamlit center column for active_page="pro"
// — route banner above a seven-tab strip (向导/脚本方案/系列/图片/视频/音频/字幕).
// Image/video/audio/subtitle panels are shared with the quick route; the plan
// drives generation, so the quick-style generate bar is not shown here.
// Tab state is lifted so the wizard can jump to the plan tab after generating
// its first-episode draft (Main.py `_navigate_to_page("plan")` parity), and the
// local-engine dashboard renders above the wizard/plan tabs when they are
// active (`_pro_tab_active` parity).
import { useState } from "react";
import { navigate } from "../../app/router";
import { RouteBanner, Tabs } from "./fields";
import { AudioPanel, ImagePanel, SubtitlePanel, VideoPanel } from "./panels";
import { LocalEngineDashboard, PlanPanel, WizardPanel } from "./proPanels";
import { SeriesPage } from "../series/SeriesPage";

export function ProPage() {
  const [tab, setTab] = useState("wizard");
  const [currentPlanId, setCurrentPlanId] = useState("");

  return (
    <div className="route-page">
      <RouteBanner
        route="pro"
        introKey="Route Pro Intro"
        linkLabelKey="Route Pro To Quick"
        onJump={() => navigate("/quick")}
      />
      {(tab === "wizard" || tab === "plan") && <LocalEngineDashboard />}
      <Tabs
        active={tab}
        onActiveChange={setTab}
        items={[
          {
            key: "wizard",
            label: "Creation Wizard",
            content: (
              <WizardPanel
                onPlanCreated={(planId) => {
                  setCurrentPlanId(planId);
                  setTab("plan");
                }}
              />
            ),
          },
          {
            key: "plan",
            label: "Script Plan",
            content: (
              <PlanPanel currentId={currentPlanId} onSelectPlan={setCurrentPlanId} />
            ),
          },
          { key: "series", label: "Series Library", content: <SeriesPage /> },
          { key: "image", label: "Image Settings", content: <ImagePanel /> },
          { key: "video", label: "Tab Video", content: <VideoPanel /> },
          { key: "audio", label: "Tab Audio", content: <AudioPanel /> },
          { key: "subtitle", label: "Tab Subtitle", content: <SubtitlePanel /> },
        ]}
      />
    </div>
  );
}
