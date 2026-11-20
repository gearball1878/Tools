"""Shared application styles and browser integration scripts."""
from nicegui import ui


def install_ui_assets() -> None:
    ui.add_css("""
        :root { --ink:#14243a; --muted:#65758b; --line:#dce5ef; --panel:#ffffff; --canvas:#eef3f8; }
        body { background:#f3f6fa; color:var(--ink); font-size:16px; }
        .q-header { background:#10243f; }
        .app-title { font-size:1.15rem; font-weight:750; letter-spacing:.01em; }
        .toolbar-select { min-width:250px; }
        .q-page { min-height:0!important; overflow:hidden; }
        .workspace { --navigator-width:320px; height:calc(100vh - 72px); min-height:0; gap:0; overflow:hidden; }
        .side-panel { width:var(--navigator-width); flex:0 0 var(--navigator-width); min-width:240px; max-width:min(720px,55vw); height:100%; min-height:0; background:#fff; overflow:auto; overflow-x:auto; }
        .navigator-resizer { width:7px; flex:0 0 7px; height:100%; cursor:col-resize; background:#f3f6fa; border-left:1px solid var(--line); border-right:1px solid var(--line); position:relative; z-index:5; transition:background .12s ease; }
        .navigator-resizer::after { content:""; position:absolute; left:2px; top:calc(50% - 26px); width:2px; height:52px; border-radius:2px; background:#9fb0c2; }
        .navigator-resizer:hover,.navigator-resizer.is-resizing { background:#dceafe; }
        .inspector { width:420px; min-width:360px; height:100%; min-height:0; background:#fff; border-left:1px solid var(--line); overflow:auto; }
        /* Keep the workspace navigation outside each tab's scroll area. */
        .canvas { min-width:0; height:100%; min-height:0; background:var(--canvas);
            overflow:hidden; display:flex; flex-direction:column; }
        .canvas > .q-tabs { flex:0 0 auto; min-height:48px; }
        .canvas > .q-tab-panels { flex:1 1 auto; min-height:0; overflow:hidden; }
        .canvas > .q-tab-panels > .q-panel { height:100%; min-height:0; overflow:auto;
            overscroll-behavior:contain; }
        .panel-heading { font-size:.76rem; font-weight:800; text-transform:uppercase; letter-spacing:.1em; color:#687a90; }
        .tree-domain { border:1px solid var(--line); border-left:5px solid var(--domain-color); border-radius:10px; }
        .tree-item { border-radius:8px; border:1px solid transparent; cursor:pointer; }
        .tree-item:hover { background:#eef5ff; border-color:#ceddf0; }
        .tree-selected { background:#e8f1ff; border-color:#8db4e8; }
        .navigator-row { min-width:0; border-radius:8px; }
        .navigator-row:hover { background:#f5f8fc; }
        .navigator-select { min-width:0; cursor:pointer; border-radius:7px; }
        .navigator-label { min-width:0; white-space:normal; overflow-wrap:anywhere; word-break:normal; hyphens:auto; line-height:1.28; }
        .navigator-actions { opacity:.22; transition:opacity .12s ease; }
        .navigator-row:hover .navigator-actions,.navigator-row:focus-within .navigator-actions,.tree-selected .navigator-actions { opacity:1; }
        .navigator-badge { max-width:110px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
        .navigator-subheading { font-size:.7rem; font-weight:800; letter-spacing:.08em; text-transform:uppercase; color:#73849a; }
        .navigator-document .q-btn__content,.simple-navigator .q-btn__content { min-width:0; }
        .navigator-document .q-btn__content > span,.simple-navigator .q-btn__content > span { min-width:0; white-space:normal; overflow-wrap:anywhere; text-align:left; }
        .side-panel .q-btn__content { min-width:0; flex-wrap:nowrap; }
        .side-panel .q-btn__content .block,.side-panel .q-item__label { min-width:0; white-space:normal; overflow-wrap:anywhere; line-height:1.25; }
        .metric { background:#fff; border:1px solid var(--line); border-radius:12px; min-width:115px; }
        .metric-value { font-size:1.35rem; font-weight:800; }
        .metric-label { font-size:.75rem; color:var(--muted); }
        .diagram-card { background:white; border:1px solid var(--line); border-radius:16px; height:calc(100vh - 315px); min-height:780px; overflow:hidden; }
        .diagram-card svg { display:block; max-width:none; }
        .empty-canvas { min-height:430px; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:10px; color:#6f8094; }
        .empty-icon { font-size:64px; color:#a8b7c7; }
        .status-pill { background:#e6f6ef; color:#08724a; border-radius:999px; padding:6px 11px; font-size:.78rem; font-weight:700; }
        .subtle { color:var(--muted); font-size:.86rem; }
        .workflow { background:#10243f; color:white; border-radius:14px; padding:12px; }
        .workflow-step { background:#ffffff14; border:1px solid #ffffff28; border-radius:10px; }
        .workflow-step:hover { background:#ffffff24; }
        .context-bar { background:#e8f1ff; border:1px solid #c4d8f1; border-radius:10px; color:#26496f; }
        .catalog-signal-card { border:1px solid #d9e2ee; border-radius:9px; background:#fbfcfe; }
        .catalog-signal-card:hover { border-color:#9dbce0; }
        .tree-select-target { min-width:0; border-radius:7px; cursor:pointer; }
        .tree-select-target:hover { background:#eef5ff; }
        .topology-participant { border:1px solid #dce5ef; border-radius:9px; background:#fbfcfe; }
        .topology-participant:hover { border-color:#9dbce0; background:#f4f8fd; }
        .topology-drawer { width:560px!important; max-width:96vw; background:#f8fafc; border-left:1px solid var(--line); }
        .topology-drawer .q-drawer__content { overflow:hidden; }
        .topology-chip { border:1px solid #bed4ec; background:#eaf3ff; border-radius:999px; }
        .topology-domain { border:1px solid #d7e1eb; border-radius:11px; background:#fff; }
        .assignment-help { background:#fff7df; border:1px solid #f2cd72; color:#714d00; border-radius:10px; }
        .connection-nav-card { border:1px solid #d9e2ec; border-radius:9px; background:#fbfcfe; }
        .connection-nav-card:hover { border-color:#8fb4dd; background:#f1f6fd; }
        .requirement-card { position:relative; overflow:hidden; cursor:pointer; transition:transform .12s ease,box-shadow .12s ease,border-color .12s ease; }
        .requirement-card::before { content:""; position:absolute; left:0; top:0; bottom:0; width:6px; background:#64748b; }
        .requirement-card:hover { transform:translateY(-1px); box-shadow:0 7px 18px #263b5520; border-color:#9dbce0; }
        .requirement-card.req-system::before { background:#2563eb; }
        .requirement-card.req-hardware::before { background:#0f9f77; }
        .requirement-card.req-mechanics::before { background:#d97706; }
        .requirement-card.req-software::before { background:#7c3aed; }
        .requirement-card.req-firmware::before { background:#be123c; }
        .isd-v-board { background:linear-gradient(160deg,#f8fbff,#ffffff); }
        .isd-v-scroll { height:min(740px,72vh); border:1px solid #d8e5f1; border-radius:12px; background:#f3f7fd; }
        .isd-v-flow { min-width:1400px; padding:16px; }
        .isd-v-column { width:320px; min-width:320px; border:1px solid #cbd9e9;
            border-radius:12px; background:white; padding:14px; max-height:680px; overflow-y:auto; }
        .isd-v-arrow { margin-top:54px; flex-shrink:0; }
        .isd-v-item { background:white!important; border:1px solid #d2dfec!important;
            border-left:4px solid #3470b6!important; border-radius:9px!important;
            padding:12px!important; text-align:left; white-space:normal; gap:6px!important; }
        .isd-v-item:hover,.isd-v-item:focus-within { background:#f6faff!important; border-color:#4984cb!important; }
        .isd-v-focused { background:#dfeeff!important; border-color:#2863a6!important; box-shadow:0 0 0 2px #80aee2; }
        .isd-v-title { padding:4px!important; font-weight:650; white-space:normal; line-height:1.4; }
        .isd-v-title .q-btn__content { width:100%; justify-content:flex-start; text-align:left; overflow-wrap:anywhere; }
        .isd-v-relation-label { font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:.04em; color:#475569; }
        .isd-v-link { padding:2px 6px!important; width:100%; min-height:28px; color:#235a9a!important; }
        .isd-v-link .q-btn__content { width:100%; justify-content:flex-start; overflow-wrap:anywhere; }
        .isd-v-empty { font-size:12px; color:#64748b; background:#f8fafc;
            border:1px dashed #cad5e2; border-radius:8px; padding:13px; width:100%; }
        .requirements-workspace { max-width:none; margin:0; min-width:0; }
        .isd-trace-viewport { overflow-x:auto; overflow-y:visible; border:1px solid #d8e5f1;
            border-radius:12px; background:#f4f8fd; scrollbar-color:#9bb5d4 transparent; }
        .isd-trace-stage { position:relative; box-sizing:border-box; width:max-content;
            min-width:100%; padding:16px 16px 42px; }
        .isd-trace-grid { position:relative; z-index:2; display:grid;
            grid-template-columns:repeat(4,minmax(235px,1fr)) repeat(3,minmax(255px,1.08fr));
            gap:44px; align-items:start; }
        .isd-trace-lane { min-width:0; border:1px solid #ccdae9; border-radius:12px;
            padding:12px; background:#ffffffeb; }
        .isd-trace-solution-lane { border-color:#9fd5c9; background:#f3fbf8ed; }
        .isd-trace-heading { min-height:45px; font-size:14px; line-height:1.3;
            border-bottom:1px solid #d7e3ef; padding-bottom:8px; }
        .isd-trace-links { position:absolute; inset:0; z-index:1; width:100%; height:100%;
            overflow:visible; pointer-events:none; }
        .isd-trace-path { fill:none; stroke:#3b74b9; stroke-width:1.4; opacity:.65;
            transition:opacity .12s ease,stroke-width .12s ease; }
        .isd-trace-path.isd-trace-editable-edge { pointer-events:stroke; cursor:pointer; stroke-width:2; }
        .isd-trace-path.is-solution { stroke:#0c8273; }
        .isd-trace-path.is-component { stroke:#b37928; }
        .isd-trace-path.isd-trace-dim { opacity:.08; }
        .isd-trace-path.isd-trace-active,.isd-trace-path.isd-trace-path-selected {
            opacity:1; stroke-width:2; }
        .isd-trace-card { position:relative; min-width:0; padding:11px!important; gap:6px!important;
            background:white!important; border:1px solid #cbd9ea!important;
            border-left:4px solid #3470b6!important; border-radius:9px!important;
            box-shadow:0 2px 5px #16365c15!important; transition:opacity .12s ease,border-color .12s ease; }
        .isd-trace-solution-card { border-left-color:#0d8778!important; }
        .isd-trace-orphan { border-left-color:#b2782e!important; }
        .isd-trace-card:hover,.isd-trace-card:focus-within { border-color:#3476c3!important; }
        .isd-trace-card.isd-trace-dim { opacity:.27; }
        .isd-trace-card.isd-trace-active { box-shadow:0 0 0 2px #6da9d1!important; }
        .isd-trace-card-title { padding:3px!important; font-size:14px!important;
            font-weight:650; white-space:normal; line-height:1.35; }
        .isd-trace-card-title .q-btn__content { width:100%; justify-content:flex-start;
            text-align:left; overflow-wrap:anywhere; }
        .isd-trace-card-meta { color:#435570; font-size:13px; line-height:1.35; overflow-wrap:anywhere; }
        .isd-trace-gap { color:#8a5300; font-size:13px; font-weight:600; }
        .isd-trace-unallocated { border:1px dashed #d3a455; border-radius:9px; background:#fffaf0; }
        .isd-trace-scopebar { padding:9px 12px;
            background:#f3f8fe; border:1px solid #c9dced; border-radius:9px; }
        .inspector:has(.isd-requirement-detail) { width:460px; min-width:410px; }
        .isd-mobile-details-btn { display:none!important; }
        .isd-trace-focus-exit { display:none!important; }
        .workspace.isd-requirements-focus .side-panel,
        .workspace.isd-requirements-focus .navigator-resizer,
        .workspace.isd-requirements-focus .inspector { display:none; }
        .workspace.isd-requirements-focus .isd-trace-focus-enter { display:none!important; }
        .workspace.isd-requirements-focus .isd-trace-focus-exit,
        .workspace.isd-requirements-focus .isd-mobile-details-btn { display:inline-flex!important; }
        .workspace.isd-requirements-focus .inspector.isd-requirements-inspector-open {
            display:block; position:fixed; top:72px; right:0; width:min(92vw,460px);
            min-width:0; height:calc(100vh - 72px); z-index:50;
            box-shadow:-10px 0 25px #172b4450;
        }
        .development-card { cursor:pointer; transition:transform .12s ease,box-shadow .12s ease,border-color .12s ease; }
        .development-card:hover { transform:translateY(-1px); box-shadow:0 7px 18px #263b5520; border-color:#9dbce0; }
        .system-definition-grid,.discipline-overview-grid,.development-grid-two { min-width:0; }
        .analysis-candidate { border-left:4px solid #c7d6e7; }
        .navigator-task { min-height:42px; border:1px solid transparent; border-radius:9px; }
        .navigator-task:hover { background:#f1f6fd; border-color:#cbdced; }
        .navigator-classification { min-height:72px; justify-content:flex-start; text-align:left; }
        .process-landscape { background:linear-gradient(180deg,#ffffff 0%,#f8fbff 100%); }
        .process-grid {
            display:grid;
            grid-template-columns:repeat(4,minmax(0,1fr));
            grid-template-areas:
                "sources analysis review requirements"
                "technical-analysis technical-review realization component-needs"
                "components interfaces standards verification"
                "proposal proposal proposal proposal";
            gap:12px;
            align-items:stretch;
        }
        .process-node {
            width:100%; min-height:92px; justify-content:flex-start; text-align:left;
            border:1px solid #cfddeb; border-radius:12px; background:#fff;
            padding:12px; box-shadow:0 2px 7px #243b5420;
            transition:opacity .15s ease,transform .15s ease,box-shadow .15s ease;
        }
        .process-node:hover { transform:translateY(-1px); box-shadow:0 7px 18px #243b5428; }
        .process-node .q-btn__content,.process-route-node .q-btn__content { width:100%; align-items:stretch; }
        .process-node-content { min-height:100%; }
        .process-gate { border-color:#e8b746; background:#fffaf0; }
        .process-step { font-size:.72rem; font-weight:800; color:#60758d; align-self:flex-start; }
        .process-path-selector .q-btn { min-height:34px; }
        .process-route-row { display:grid; align-items:stretch; overflow-x:auto; padding:2px 1px 6px; }
        .process-route-node {
            width:100%; min-height:116px; justify-content:flex-start; text-align:left;
            border:2px solid #8fb6e5; border-radius:12px; background:#fff;
            padding:12px; box-shadow:0 3px 10px #174ea61f;
            transition:transform .15s ease,box-shadow .15s ease,border-color .15s ease;
        }
        .process-route-node:hover { transform:translateY(-2px); border-color:#174ea6; box-shadow:0 8px 20px #174ea62b; }
        .process-route-arrow { display:flex; align-items:center; justify-content:center; min-width:38px; }
        .process-route-turn { min-height:28px; }
        .document-context-preview textarea { line-height:1.45; font-family:ui-monospace,SFMono-Regular,Consolas,monospace; }
        .process-source { grid-area:sources; }
        .process-analysis { grid-area:analysis; }
        .process-review { grid-area:review; }
        .process-requirements { grid-area:requirements; }
        .process-technical-analysis { grid-area:technical-analysis; border-color:#57a8a0; background:#f3fffd; }
        .process-technical-review { grid-area:technical-review; border-color:#e8b746; background:#fffaf0; }
        .process-realization { grid-area:realization; border-color:#8b5cf6; background:#faf7ff; }
        .process-component-needs { grid-area:component-needs; }
        .process-components { grid-area:components; }
        .process-interfaces { grid-area:interfaces; }
        .process-standards { grid-area:standards; }
        .process-verification { grid-area:verification; }
        .process-proposal { grid-area:proposal; }
        .workflow-task { border:1px solid transparent; border-radius:9px; }
        .workflow-task:hover { background:#fff9eb; border-color:#f0d18a; }
        .workflow-detail-grid { grid-template-columns:repeat(2,minmax(0,1fr))!important; }
        .realization-card { border-left:5px solid #7c3aed; background:linear-gradient(90deg,#faf7ff 0,#fff 26%); }
        .realization-flow { display:grid; grid-template-columns:minmax(0,1fr) 32px minmax(0,1.25fr) 32px minmax(0,1fr); align-items:center; gap:8px; }
        .realization-stage { min-width:0; padding:11px; border:1px solid #d8e2ec; border-radius:10px; background:#fff; }
        .ai-assistant-panel { height:100vh; max-height:100vh; border-radius:0; transition:width .18s ease; }
        .ai-assistant-normal { width:min(760px,96vw); }
        .ai-assistant-max { width:min(1180px,100vw); }
        .assistant-chat-scroll { min-height:280px; height:calc(100vh - 370px); }
        .assistant-user-message { max-width:86%; background:#e8f1ff; border:1px solid #bdd5ef; }
        .assistant-ai-message { background:#fff; border:1px solid var(--line); }
        .canvas-viewbar { background:#fff; border:1px solid var(--line); border-radius:12px; padding:10px 12px; }
        .color-palette { display:grid; grid-template-columns:repeat(8,minmax(38px,1fr)); gap:9px; padding:11px; background:#f8fafc; border:1px solid #d8e2ec; border-radius:11px; }
        .color-swatch { appearance:none; display:flex; align-items:center; justify-content:center; width:100%; height:40px; min-width:38px; padding:0; border-radius:7px; color:white; border:2px solid transparent; cursor:pointer; transition:transform .12s ease,box-shadow .12s ease; }
        .color-swatch:hover { transform:translateY(-1px); box-shadow:0 3px 9px #27364a33; }
        .color-swatch:focus-visible { outline:3px solid #174ea6; outline-offset:2px; }
        .color-swatch-selected { border-color:white; outline:3px solid #174ea6; outline-offset:1px; box-shadow:0 3px 9px #27364a33; }
        .color-swatch .q-icon { color:white; filter:drop-shadow(0 1px 1px #0008); }
        .simple-workspace { max-width:1500px; margin:0 auto; }
        .cascade-map { background:linear-gradient(180deg,#fff 0%,#f6f9fd 100%); }
        .cascade-source-row { position:relative; }
        .cascade-step {
            width:min(220px,23%); min-height:106px; border:1px solid #c9d9ea;
            border-radius:14px; background:#fff; box-shadow:0 3px 10px #263b5417;
        }
        .cascade-step + .cascade-step::before {
            content:"→"; position:absolute; margin-left:-30px; color:#6f89a6;
            font-size:1.45rem; font-weight:700;
        }
        .cascade-step .q-btn__content { display:flex; flex-direction:column; gap:3px; }
        .discipline-tree-grid { grid-template-columns:repeat(4,minmax(0,1fr))!important; }
        .discipline-branch {
            min-height:118px; width:100%; justify-content:flex-start; text-align:left;
            border:1px solid #d3deea; border-top:5px solid #64748b; border-radius:13px;
            background:#fff; padding:14px;
        }
        .discipline-branch .q-btn__content { width:100%; align-items:stretch; }
        .branch-system { border-top-color:#2563eb; }
        .branch-hardware { border-top-color:#0f9f77; }
        .branch-mechanics { border-top-color:#d97706; }
        .branch-software { border-top-color:#7c3aed; }
        .system-summary-card { border-left:5px solid #2563eb; }
        .compact-system-grid { grid-template-columns:repeat(3,minmax(0,1fr))!important; }
        .document-chip-row { max-height:90px; overflow:auto; }
        .analysis-overview { background:linear-gradient(180deg,#fff 0%,#fafcff 100%); }
        .analysis-section-title { font-size:.78rem; font-weight:800; text-transform:uppercase; letter-spacing:.08em; color:#5e7188; }
        .analysis-summary-grid { grid-template-columns:repeat(2,minmax(0,1fr))!important; }
        .analysis-summary-tile { border:1px solid #dce5ef; border-radius:11px; background:#f8fafc; padding:12px; gap:6px; }
        .discipline-analysis-grid { grid-template-columns:repeat(4,minmax(0,1fr))!important; }
        .analysis-count-tile { border:1px solid #d8e3ef; border-radius:12px; background:#fff; padding:13px; gap:2px; }
        .analysis-detail-grid { grid-template-columns:repeat(3,minmax(0,1fr))!important; }
        .requirements-filterbar { background:var(--canvas); padding:4px 0; }
        .standards-grid { grid-template-columns:repeat(2,minmax(0,1fr))!important; }
        .standard-card { cursor:pointer; transition:transform .12s ease,box-shadow .12s ease; }
        .standard-card:hover { transform:translateY(-1px); box-shadow:0 7px 18px #263b5520; }
        .simple-navigator .q-btn__content { width:100%; flex-wrap:nowrap; }
        @media (max-width:1250px) {
            .process-grid {
                grid-template-columns:repeat(2,minmax(0,1fr));
                grid-template-areas:
                    "sources analysis"
                    "review requirements"
                    "technical-analysis technical-review"
                    "realization component-needs"
                    "components interfaces"
                    "standards verification"
                "proposal proposal";
            }
            .discipline-tree-grid,.discipline-analysis-grid { grid-template-columns:repeat(2,minmax(0,1fr))!important; }
            .analysis-detail-grid { grid-template-columns:1fr!important; }
        }
        @media (max-width:1100px) {
            .inspector { display:none; }
            .inspector.isd-mobile-details-open { display:block; position:fixed; top:72px; right:0;
                width:min(92vw,440px); min-width:0; height:calc(100vh - 72px);
                z-index:50; box-shadow:-10px 0 25px #172b4450; }
            .isd-mobile-details-btn { display:inline-flex!important; }
        }
        @media (max-width:760px) {
            .process-grid { display:flex; flex-direction:column; }
            .process-route-row { grid-template-columns:1fr!important; gap:8px; overflow:visible; }
            .process-route-arrow { display:none; }
            .process-route-turn { justify-content:center; padding-right:0; }
            .workflow-detail-grid { grid-template-columns:1fr!important; }
            .realization-flow { grid-template-columns:1fr; }
            .realization-flow > .q-icon { transform:rotate(90deg); justify-self:center; }
            .ai-assistant-normal,.ai-assistant-max { width:100vw; }
            .system-definition-grid,.discipline-overview-grid,.development-grid-two,
            .discipline-tree-grid,.discipline-analysis-grid,
            .standards-grid,.analysis-summary-grid,.compact-system-grid { grid-template-columns:1fr!important; }
            .cascade-source-row { flex-direction:column; }
            .cascade-step { width:100%; }
            .cascade-step + .cascade-step::before { display:none; }
        }
    """)
    ui.add_head_html("""
      <script src="/xped-static/elk.bundled.js"></script>
      <script src="/xped-static/architecture_canvas.js?v=0.37.3"></script>
      <script src="/xped-static/requirements_graph.js?v=0.36.4"></script>
      <script>
        window.xpedCanvasScale = function(button, scale) {
          const canvas = button.closest('.xped-interactive-canvas');
          const stage = canvas.querySelector('.canvas-stage');
          const svg = stage.querySelector('svg');
          if (!svg) return;
          const value = Math.max(0.08, Math.min(2.5, scale));
          const box = svg.viewBox.baseVal;
          stage.dataset.scale = value;
          svg.style.width = `${box.width * value}px`;
          svg.style.height = `${box.height * value}px`;
          canvas.classList.toggle('semantic-overview', value < 0.48);
          canvas.classList.toggle('semantic-medium', value >= 0.48 && value < 0.78);
          canvas.classList.toggle('semantic-detail', value >= 0.78);
        };
        window.xpedCanvasZoom = function(button, factor) {
          const stage = button.closest('.xped-interactive-canvas').querySelector('.canvas-stage');
          if (!stage.querySelector('svg')) return;
          xpedCanvasScale(button, Number(stage.dataset.scale || 1) * factor);
        };
        window.xpedCanvasFit = function(button) {
          const canvas = button.closest('.xped-interactive-canvas');
          const viewport = canvas.querySelector('.canvas-viewport');
          const svg = canvas.querySelector('svg');
          if (!svg) return;
          const box = svg.viewBox.baseVal;
          xpedCanvasScale(button, Math.min((viewport.clientWidth - 24) / box.width, (viewport.clientHeight - 24) / box.height, 1));
          viewport.scrollTo(0, 0);
        };
        window.xpedCanvasWheel = function(event, viewport) {
          if (!event.ctrlKey) return;
          event.preventDefault();
          const button = viewport.closest('.xped-interactive-canvas').querySelector('button');
          xpedCanvasZoom(button, event.deltaY < 0 ? 1.12 : 0.893);
        };
        window.isdApplyNavigatorWidth = function() {
          const saved = Number(window.localStorage.getItem('isd.navigator.width') || 320);
          const width = Math.max(240, Math.min(saved, Math.min(720, window.innerWidth * 0.55)));
          document.querySelectorAll('.workspace').forEach(
            workspace => workspace.style.setProperty('--navigator-width', `${width}px`)
          );
        };
        if (!window.__isdNavigatorResizeInstalled) {
          window.__isdNavigatorResizeInstalled = true;
          let active = null;
          document.addEventListener('mousedown', event => {
            const handle = event.target.closest('.navigator-resizer');
            if (!handle) return;
            const workspace = handle.closest('.workspace');
            const panel = workspace && workspace.querySelector('.side-panel');
            if (!workspace || !panel) return;
            active = {handle, workspace, startX:event.clientX, startWidth:panel.getBoundingClientRect().width};
            handle.classList.add('is-resizing');
            document.body.style.userSelect = 'none';
            event.preventDefault();
          });
          document.addEventListener('mousemove', event => {
            if (!active) return;
            const width = Math.max(240, Math.min(active.startWidth + event.clientX - active.startX, Math.min(720, window.innerWidth * 0.55)));
            active.workspace.style.setProperty('--navigator-width', `${width}px`);
          });
          document.addEventListener('mouseup', () => {
            if (!active) return;
            const width = Math.round(active.workspace.querySelector('.side-panel').getBoundingClientRect().width);
            window.localStorage.setItem('isd.navigator.width', String(width));
            active.handle.classList.remove('is-resizing');
            document.body.style.userSelect = '';
            active = null;
          });
          window.addEventListener('resize', window.isdApplyNavigatorWidth);
          const observeNavigator = () => {
            if (!document.body) return;
            new MutationObserver(window.isdApplyNavigatorWidth).observe(
              document.body, {childList:true, subtree:true}
            );
            window.isdApplyNavigatorWidth();
          };
          if (document.body) observeNavigator();
          else window.addEventListener('DOMContentLoaded', observeNavigator, {once:true});
        }
        window.setTimeout(window.isdApplyNavigatorWidth, 0);
      </script>
    """)
