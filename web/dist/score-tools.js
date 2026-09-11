import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const settingId = "Olm.YuE2.ScoreTools";
const tabId = "olm-yue2-score";
let ready = false;
let enabled = false;
let panel;
let revision = 0;

async function setEnabled(value) {
  if (!ready) return;
  enabled = Boolean(value);
  const current = ++revision;
  if (!enabled) {
    app.extensionManager.sidebarTab.unregisterSidebarTab(tabId);
    panel = undefined;
    return;
  }
  if (panel) return;
  try {
    const { createScorePanel } = await import("./score-panel.mjs");
    if (!enabled || current !== revision) return;
    panel = createScorePanel(app);
    app.extensionManager.sidebarTab.registerSidebarTab({
      id: tabId,
      icon: "pi pi-headphones",
      title: "YuE2 Score",
      tooltip: "Inspect YuE2 scores and preview ABC edits",
      type: "custom",
      render: (element) => panel?.mount(element),
      destroy: () => panel?.destroy(),
    });
  } catch (error) {
    if (current !== revision) return;
    panel?.destroy();
    panel = undefined;
    console.warn("[YuE2] Score tools could not load. ABC text and generation still work.", error);
    app.extensionManager.toast.add({ severity: "warn", summary: "YuE2 score tools unavailable",
      detail: "Refresh the page to retry. ABC text and generation still work.", life: 8000 });
  }
}

app.registerExtension({
  name: "Olm.YuE2.ScoreTools",
  settings: [{
    id: settingId,
    name: "Enable optional score tools",
    type: "boolean",
    defaultValue: false,
    category: ["YuE2", "Score", "Enabled"],
    tooltip: "Adds a local notation sidebar for Score Preview and ABC Editor nodes. Generation does not require it.",
    onChange: setEnabled,
  }],
  setup() {
    ready = true;
    api.addEventListener("executed", ({ detail }) => {
      if (detail.output?.yue2_score) panel?.refresh();
    });
    return setEnabled(app.extensionManager.setting.get(settingId));
  },
  beforeConfigureGraph() { panel?.clear(); },
  afterConfigureGraph() { panel?.refresh(); },
});
