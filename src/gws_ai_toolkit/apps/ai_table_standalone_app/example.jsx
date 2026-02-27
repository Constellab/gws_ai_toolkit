import { useState, useRef } from "react";

const PALETTE = `
  :root {
    --accent-1: #f7fdfc; --accent-2: #e9f8f5; --accent-3: #d3f0eb;
    --accent-4: #bde9e1; --accent-5: #a7e1d7; --accent-6: #7cd2c4;
    --accent-7: #50c3b0; --accent-8: #25b49c; --accent-9: #1d907d;
    --accent-10: #166c5e; --accent-11: #0e483e; --accent-12: #0b362f;
    --secondary-1: #f9f8fd; --secondary-2: #f3f1fc; --secondary-3: #eeebfa;
    --secondary-6: #d1c9f1; --secondary-7: #c5bbee; --secondary-8: #a69bd3;
    --secondary-9: #877bb8; --secondary-10: #675a9d; --secondary-11: #584a90;
    --tertiary-5: #ffa9d9; --tertiary-7: #e176b2; --tertiary-9: #a63b77;
  }
`;

// ── Sample data ───────────────────────────────────────────────────────────
const IRIS = [
    [5.1, 3.5, 1.4, 0.2, "Setosa"], [4.9, 3.0, 1.4, 0.2, "Setosa"],
    [4.7, 3.2, 1.3, 0.2, "Setosa"], [4.6, 3.1, 1.5, 0.2, "Setosa"],
    [5.0, 3.6, 1.4, 0.2, "Setosa"], [5.4, 3.9, 1.7, 0.4, "Setosa"],
    [4.6, 3.4, 1.4, 0.3, "Setosa"], [5.0, 3.4, 1.5, 0.2, "Setosa"],
    [4.4, 2.9, 1.4, 0.2, "Setosa"], [4.9, 3.1, 1.5, 0.1, "Setosa"],
    [6.3, 3.3, 6.0, 2.5, "Virginica"], [5.8, 2.7, 5.1, 1.9, "Virginica"],
    [7.1, 3.0, 5.9, 2.1, "Virginica"], [6.3, 2.9, 5.6, 1.8, "Virginica"],
    [5.7, 2.5, 5.0, 2.0, "Versicolor"], [5.8, 2.8, 5.1, 2.4, "Versicolor"],
    [6.4, 3.2, 5.3, 2.3, "Versicolor"], [6.5, 3.0, 5.5, 1.8, "Versicolor"],
];
const COLS = ["sepal_length", "sepal_width", "petal_length", "petal_width", "variety"];

const TABLES = [
    { id: "iris_3", label: "irisgood_3", sheets: ["Sheet1"] },
    { id: "sales_q1", label: "sales_Q1.xlsx", sheets: ["Jan", "Feb", "Mar"] },
    { id: "inventory", label: "inventory_2024.xlsx", sheets: ["Electronics", "Clothing"] },
];

const CHAT_MSGS = [
    { role: "assistant", text: "Hi! I'm your AI analyst. Ask me anything about this dataset." },
    { role: "user", text: "What's the average sepal length?" },
    { role: "assistant", text: "The average sepal length across all 150 rows is **5.84 cm**. Virginica has the highest average at 6.59 cm, while Setosa has the lowest at 5.01 cm." },
];

const STATS = [
    { col: "sepal_length", min: 4.3, max: 7.9, mean: 5.84, std: 0.83 },
    { col: "sepal_width", min: 2.0, max: 4.4, mean: 3.06, std: 0.44 },
    { col: "petal_length", min: 1.0, max: 6.9, mean: 3.76, std: 1.77 },
    { col: "petal_width", min: 0.1, max: 2.5, mean: 1.20, std: 0.76 },
];

// ── Icons ─────────────────────────────────────────────────────────────────
const Icon = ({ d, size = 16, stroke = "currentColor", fill = "none" }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill={fill} stroke={stroke} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
        {typeof d === "string" ? <path d={d} /> : d}
    </svg>
);
const IconChat = () => <Icon d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />;
const IconStats = () => <Icon d={<><line x1="18" y1="20" x2="18" y2="10" /><line x1="12" y1="20" x2="12" y2="4" /><line x1="6" y1="20" x2="6" y2="14" /></>} />;
const IconTable = () => <Icon d={<><rect x="3" y="3" width="18" height="18" rx="2" /><line x1="3" y1="9" x2="21" y2="9" /><line x1="3" y1="15" x2="21" y2="15" /><line x1="9" y1="3" x2="9" y2="21" /></>} />;
const IconFilter = () => <Icon d="M22 3H2l8 9.46V19l4 2v-8.54z" />;
const IconSort = () => <Icon d="M3 6h18M7 12h10M11 18h2" />;
const IconSearch = () => <Icon d="M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z" />;
const IconDownload = () => <Icon d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3" />;
const IconExtract = () => <Icon d="M9 11l3 3L22 4M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />;
const IconChevron = ({ dir = "down" }) => {
    const r = { down: 0, up: 180, right: 90, left: -90 }[dir];
    return (
        <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"
            style={{ transform: `rotate(${r}deg)`, transition: "transform .2s" }}>
            <polyline points="6 9 12 15 18 9" />
        </svg>
    );
};
const IconClose = () => <Icon d="M18 6L6 18M6 6l12 12" size={14} />;
const IconSend = () => <Icon d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" size={15} />;
const IconSheet = () => <Icon d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6z" size={13} />;
const IconPlus = () => <Icon d="M12 5v14M5 12h14" size={14} />;

// ── Variety badge ─────────────────────────────────────────────────────────
const varColor = { Setosa: "accent", Virginica: "secondary", Versicolor: "tertiary" };
const Badge = ({ v }) => {
    const c = varColor[v] || "accent";
    const styles = {
        accent: { bg: "var(--accent-2)", color: "var(--accent-10)", border: "var(--accent-4)" },
        secondary: { bg: "var(--secondary-2)", color: "var(--secondary-11)", border: "var(--secondary-6)" },
        tertiary: { bg: "#fff4fa", color: "var(--tertiary-9)", border: "#ffd4ec" },
    };
    const s = styles[c];
    return (
        <span style={{
            padding: "2px 8px", borderRadius: 20, fontSize: 11, fontWeight: 600,
            background: s.bg, color: s.color, border: `1px solid ${s.border}`, letterSpacing: .3
        }}>
            {v}
        </span>
    );
};

// ── Mini bar for stats ────────────────────────────────────────────────────
const MiniBar = ({ val, max, color }) => (
    <div style={{ height: 4, background: "#eef", borderRadius: 99, overflow: "hidden", flex: 1 }}>
        <div style={{ height: "100%", width: `${(val / max) * 100}%`, background: color, borderRadius: 99, transition: "width .5s" }} />
    </div>
);

// ── Main App ──────────────────────────────────────────────────────────────
export default function App() {
    const [activeTable, setActiveTable] = useState(TABLES[0]);
    const [activeSheet, setActiveSheet] = useState(TABLES[0].sheets[0]);
    const [panel, setPanel] = useState(null); // "chat" | "stats" | null
    const [tableDropOpen, setTableDropOpen] = useState(false);
    const [sheetDropOpen, setSheetDropOpen] = useState(false);
    const [search, setSearch] = useState("");
    const [chatInput, setChatInput] = useState("");
    const [messages, setMessages] = useState(CHAT_MSGS);
    const chatEnd = useRef(null);

    const filtered = IRIS.filter(r =>
        r.some(c => String(c).toLowerCase().includes(search.toLowerCase()))
    );

    const switchTable = (t) => {
        setActiveTable(t);
        setActiveSheet(t.sheets[0]);
        setTableDropOpen(false);
        setSheetDropOpen(false);
    };

    const togglePanel = (p) => setPanel(prev => prev === p ? null : p);

    const sendMsg = () => {
        if (!chatInput.trim()) return;
        setMessages(m => [...m, { role: "user", text: chatInput }]);
        setChatInput("");
        setTimeout(() => {
            setMessages(m => [...m, { role: "assistant", text: "Great question! Let me analyze that for you… (demo mode)" }]);
            chatEnd.current?.scrollIntoView({ behavior: "smooth" });
        }, 600);
    };

    return (
        <>
            <style>{PALETTE}{`
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');
        *, *::before, *::after { box-sizing: border-box; margin:0; padding:0; }
        body { font-family: 'Plus Jakarta Sans', sans-serif; background: var(--accent-1); color: #1a2b28; }

        /* Scrollbar */
        ::-webkit-scrollbar { width:6px; height:6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: var(--accent-4); border-radius:99px; }

        /* Topbar */
        .topbar {
          display:flex; align-items:center; gap:12px;
          padding: 0 20px; height:56px;
          background: #fff;
          border-bottom: 1px solid var(--accent-3);
          position: sticky; top:0; z-index:100;
        }
        .logo {
          display:flex; align-items:center; gap:8px;
          font-weight:800; font-size:15px; color: var(--accent-11);
          letter-spacing:-.3px; white-space:nowrap;
          padding-right:16px; border-right:1px solid var(--accent-3);
        }
        .logo-dot { width:8px; height:8px; border-radius:50%; background:var(--accent-8); }

        /* Table selector */
        .table-selector { position:relative; }
        .table-pill {
          display:flex; align-items:center; gap:6px;
          padding: 5px 10px 5px 8px;
          background: var(--accent-1); border: 1px solid var(--accent-4);
          border-radius: 8px; cursor:pointer; user-select:none;
          font-size:13px; font-weight:600; color:var(--accent-11);
          transition: background .15s, border-color .15s;
        }
        .table-pill:hover { background:var(--accent-2); border-color:var(--accent-6); }
        .table-icon { color: var(--accent-8); }
        .table-dropdown {
          position:absolute; top:calc(100% + 6px); left:0; min-width:220px;
          background:#fff; border:1px solid var(--accent-3);
          border-radius:12px; box-shadow:0 8px 32px #1d907d18;
          overflow:hidden; z-index:200;
          animation: fadeDown .15s ease;
        }
        @keyframes fadeDown { from { opacity:0; transform:translateY(-4px); } to { opacity:1; transform:translateY(0); } }
        .dropdown-header { padding:8px 12px 6px; font-size:10px; font-weight:700; color:var(--accent-9); letter-spacing:.8px; text-transform:uppercase; }
        .table-item {
          display:flex; align-items:center; gap:8px;
          padding: 8px 12px; cursor:pointer;
          font-size:13px; font-weight:500; color:var(--accent-12);
          transition:background .1s;
        }
        .table-item:hover { background:var(--accent-1); }
        .table-item.active { background:var(--accent-2); color:var(--accent-9); font-weight:700; }
        .sheet-chips { display:flex; gap:4px; margin-top:2px; flex-wrap:wrap; }
        .sheet-chip {
          font-size:10px; padding:1px 6px; border-radius:99px;
          background:var(--accent-3); color:var(--accent-10); font-weight:600;
        }

        /* Sheet tabs */
        .sheet-tabs { display:flex; align-items:center; gap:2px; }
        .sheet-tab {
          display:flex; align-items:center; gap:4px;
          padding:4px 10px; border-radius:6px; cursor:pointer;
          font-size:12px; font-weight:600; color:#6b7e7c;
          transition:all .15s;
        }
        .sheet-tab:hover { background:var(--accent-2); color:var(--accent-10); }
        .sheet-tab.active {
          background:var(--accent-3); color:var(--accent-9);
        }

        .spacer { flex:1; }

        /* Actions */
        .actions { display:flex; align-items:center; gap:4px; }
        .action-btn {
          display:flex; align-items:center; gap:5px;
          padding:5px 10px; border-radius:7px; border:none; cursor:pointer;
          font-family:inherit; font-size:12px; font-weight:600;
          background:transparent; color:#5a7470;
          transition:all .15s;
        }
        .action-btn:hover { background:var(--accent-2); color:var(--accent-9); }
        .add-file-btn {
          display:flex; align-items:center; gap:5px;
          padding:5px 11px; border-radius:8px; cursor:pointer;
          font-family:'Plus Jakarta Sans',sans-serif; font-size:12px; font-weight:700;
          color: var(--accent-9); background: var(--accent-2);
          border: 1px dashed var(--accent-6);
          transition:all .15s; white-space:nowrap;
        }
        .add-file-btn:hover { background:var(--accent-3); border-color:var(--accent-8); color:var(--accent-10); }

        /* Panel toggles */
        .action-sep { width:1px; height:18px; background:var(--accent-3); margin:0 2px; }
          display:flex; align-items:center; gap:5px;
          padding:5px 12px; border-radius:8px; border:none; cursor:pointer;
          font-family:inherit; font-size:12px; font-weight:700;
          transition:all .2s;
        }
        .panel-toggle.chat {
          background: var(--secondary-2); color:var(--secondary-11);
          border:1px solid var(--secondary-6);
        }
        .panel-toggle.chat:hover, .panel-toggle.chat.active {
          background:var(--secondary-11); color:#fff;
        }
        .panel-toggle.stats {
          background:var(--accent-2); color:var(--accent-9);
          border:1px solid var(--accent-5);
        }
        .panel-toggle.stats:hover, .panel-toggle.stats.active {
          background:var(--accent-9); color:#fff;
        }

        /* Layout */
        .layout { display:flex; height:calc(100vh - 56px); overflow:hidden; }

        /* Table area */
        .table-area { flex:1; display:flex; flex-direction:column; overflow:hidden; }

        /* Toolbar */
        .toolbar {
          display:flex; align-items:center; gap:8px;
          padding:10px 20px;
          border-bottom:1px solid var(--accent-3);
          background:#fff;
        }
        .search-wrap {
          display:flex; align-items:center; gap:7px;
          padding:5px 10px; border-radius:8px;
          border:1px solid var(--accent-3); background:var(--accent-1);
          font-size:13px; color:#6b8480;
          flex:1; max-width:280px;
        }
        .search-wrap input {
          border:none; background:transparent; outline:none;
          font-family:inherit; font-size:13px; width:100%; color:var(--accent-12);
        }
        .search-wrap input::placeholder { color:#9bb8b3; }
        .row-count {
          margin-left:auto; font-size:12px; color:#9bb8b3; font-weight:500;
        }
        .row-count strong { color:var(--accent-9); }

        /* Table */
        .table-scroll { flex:1; overflow:auto; }
        table { width:100%; border-collapse:collapse; font-size:13px; }
        thead { position:sticky; top:0; z-index:10; }
        th {
          padding:10px 16px; text-align:left;
          background:#fff; border-bottom:2px solid var(--accent-3);
          font-size:11px; font-weight:700; color:var(--accent-9);
          letter-spacing:.6px; text-transform:uppercase; white-space:nowrap;
        }
        th .th-inner { display:flex; align-items:center; gap:4px; }
        th .sort-icon { color:var(--accent-5); opacity:.6; }
        tbody tr {
          border-bottom:1px solid var(--accent-2);
          transition:background .1s;
        }
        tbody tr:hover { background:var(--accent-1); }
        td { padding:9px 16px; color:#2a3e3c; white-space:nowrap; }
        td.num { color:var(--accent-10); font-weight:500; font-variant-numeric:tabular-nums; }

        /* Right panel */
        .panel {
          width:340px; min-width:340px; max-width:340px;
          display:flex; flex-direction:column;
          background:#fff; border-left:1px solid var(--accent-3);
          animation:slideIn .2s ease;
        }
        @keyframes slideIn { from { transform:translateX(30px); opacity:0; } to { transform:translateX(0); opacity:1; } }
        .panel-head {
          display:flex; align-items:center; justify-content:space-between;
          padding:14px 16px 12px;
          border-bottom:1px solid var(--accent-3);
        }
        .panel-title { font-size:14px; font-weight:800; color:var(--accent-11); }
        .panel-close {
          background:none; border:none; cursor:pointer; color:#9bb8b3;
          display:flex; align-items:center; padding:2px;
          border-radius:4px; transition:color .15s;
        }
        .panel-close:hover { color:var(--accent-9); }

        /* Chat */
        .chat-body { flex:1; overflow-y:auto; padding:14px 14px 0; display:flex; flex-direction:column; gap:10px; }
        .chat-msg { display:flex; flex-direction:column; gap:3px; }
        .chat-msg.user { align-items:flex-end; }
        .chat-bubble {
          max-width:85%; padding:8px 12px; border-radius:12px;
          font-size:13px; line-height:1.5;
        }
        .chat-msg.assistant .chat-bubble {
          background:var(--accent-1); border:1px solid var(--accent-3);
          color:var(--accent-12); border-radius:4px 12px 12px 12px;
        }
        .chat-msg.user .chat-bubble {
          background:var(--secondary-11); color:#fff;
          border-radius:12px 4px 12px 12px;
        }
        .chat-input-area {
          padding:12px; border-top:1px solid var(--accent-3);
          display:flex; gap:8px; align-items:flex-end;
        }
        .chat-input {
          flex:1; padding:8px 12px; border-radius:10px;
          border:1px solid var(--accent-4); background:var(--accent-1);
          font-family:inherit; font-size:13px; outline:none; resize:none;
          color:var(--accent-12); line-height:1.4;
          transition:border-color .15s;
        }
        .chat-input:focus { border-color:var(--accent-7); }
        .chat-send {
          padding:8px 12px; border-radius:10px;
          background:var(--accent-9); color:#fff;
          border:none; cursor:pointer; font-family:inherit;
          display:flex; align-items:center; justify-content:center;
          transition:background .15s;
        }
        .chat-send:hover { background:var(--accent-10); }

        /* Stats */
        .stats-body { flex:1; overflow-y:auto; padding:14px; display:flex; flex-direction:column; gap:10px; }
        .stat-card {
          padding:12px 14px; border-radius:10px;
          border:1px solid var(--accent-3); background:var(--accent-1);
        }
        .stat-col { font-size:12px; font-weight:700; color:var(--accent-9); margin-bottom:8px; text-transform:uppercase; letter-spacing:.5px; }
        .stat-row { display:flex; align-items:center; gap:8px; margin-bottom:4px; }
        .stat-label { font-size:11px; color:#9bb8b3; font-weight:500; width:32px; }
        .stat-val { font-size:12px; font-weight:700; color:var(--accent-11); width:38px; text-align:right; font-variant-numeric:tabular-nums; }
        .variety-dist { padding:12px 14px; border-radius:10px; border:1px solid var(--secondary-6); background:var(--secondary-1); }
        .variety-row { display:flex; align-items:center; gap:8px; margin-bottom:6px; }
        .variety-label { font-size:12px; font-weight:600; width:76px; }
        .variety-bar { flex:1; height:8px; border-radius:99px; overflow:hidden; background:var(--secondary-2); }
        .variety-bar-fill { height:100%; border-radius:99px; transition:width .5s; }
        .variety-pct { font-size:11px; font-weight:700; color:var(--secondary-10); width:30px; text-align:right; }
      `}</style>

            {/* TOP BAR */}
            <div className="topbar">
                <div className="logo">
                    <div className="logo-dot" />
                    Table Analyst
                </div>

                {/* Table selector */}
                <div className="table-selector">
                    <div className="table-pill" onClick={() => { setTableDropOpen(o => !o); setSheetDropOpen(false); }}>
                        <span className="table-icon"><IconTable /></span>
                        <span>{activeTable.label}</span>
                        <IconChevron dir={tableDropOpen ? "up" : "down"} />
                    </div>
                    {tableDropOpen && (
                        <div className="table-dropdown">
                            <div className="dropdown-header">Tables</div>
                            {TABLES.map(t => (
                                <div key={t.id} className={`table-item${t.id === activeTable.id ? " active" : ""}`} onClick={() => switchTable(t)}>
                                    <span style={{ color: "var(--accent-7)" }}><IconTable /></span>
                                    <div>
                                        <div>{t.label}</div>
                                        <div className="sheet-chips">
                                            {t.sheets.map(s => <span key={s} className="sheet-chip">{s}</span>)}
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                {/* Sheet selector (if multiple sheets) */}
                {activeTable.sheets.length > 1 && (
                    <div className="table-selector">
                        <div className="table-pill" onClick={(e) => { e.stopPropagation(); setSheetDropOpen(o => !o); setTableDropOpen(false); }}>
                            <span className="table-icon" style={{ color: "var(--secondary-8)" }}><IconSheet /></span>
                            <span style={{ color: "var(--secondary-11)" }}>{activeSheet}</span>
                            <IconChevron dir={sheetDropOpen ? "up" : "down"} />
                        </div>
                        {sheetDropOpen && (
                            <div className="table-dropdown" style={{ borderColor: "var(--secondary-6)" }}>
                                <div className="dropdown-header" style={{ color: "var(--secondary-9)" }}>Feuilles</div>
                                {activeTable.sheets.map(s => (
                                    <div key={s} className={`table-item${s === activeSheet ? " active" : ""}`}
                                        style={s === activeSheet ? { background: "var(--secondary-2)", color: "var(--secondary-10)" } : {}}
                                        onClick={(e) => { e.stopPropagation(); setActiveSheet(s); setSheetDropOpen(false); }}>
                                        <span style={{ color: "var(--secondary-7)" }}><IconSheet /></span>
                                        {s}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                )}

                {/* Add file button */}
                <label className="add-file-btn" title="Importer un fichier Excel">
                    <input type="file" accept=".xlsx,.xls,.csv" style={{ display: "none" }}
                        onChange={e => {
                            const file = e.target.files?.[0];
                            if (!file) return;
                            const newTable = { id: file.name, label: file.name, sheets: ["Sheet1"] };
                            TABLES.push(newTable);
                            switchTable(newTable);
                            e.target.value = "";
                        }}
                    />
                    <IconPlus /> Importer
                </label>

                <div className="spacer" />

                {/* Panel toggles */}
                <button className={`panel-toggle chat${panel === "chat" ? " active" : ""}`} onClick={() => togglePanel("chat")}>
                    <IconChat /> Chat
                </button>
                <button className={`panel-toggle stats${panel === "stats" ? " active" : ""}`} onClick={() => togglePanel("stats")}>
                    <IconStats /> Stats
                </button>
            </div>

            {/* LAYOUT */}
            <div className="layout" onClick={() => { tableDropOpen && setTableDropOpen(false); sheetDropOpen && setSheetDropOpen(false); }}>
                {/* TABLE AREA */}
                <div className="table-area">
                    {/* Toolbar */}
                    <div className="toolbar">
                        <div className="search-wrap">
                            <IconSearch />
                            <input placeholder="Search…" value={search} onChange={e => setSearch(e.target.value)} />
                        </div>

                        <div className="actions">
                            <div className="action-sep" />
                            <button className="action-btn"><IconFilter /> Filter</button>
                            <button className="action-btn"><IconSort /> Sort</button>
                            <div className="action-sep" />
                            <button className="action-btn"><IconExtract /> Extract selection</button>
                            <button className="action-btn"><IconDownload /> Export</button>
                        </div>

                        <div className="row-count">
                            <strong>{filtered.length}</strong> / 150 rows
                        </div>
                    </div>

                    {/* Table */}
                    <div className="table-scroll">
                        <table>
                            <thead>
                                <tr>
                                    {COLS.map(c => (
                                        <th key={c}>
                                            <div className="th-inner">
                                                {c.replace("_", " ")}
                                                <span className="sort-icon"><IconSort /></span>
                                            </div>
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {filtered.map((row, i) => (
                                    <tr key={i}>
                                        {row.map((cell, j) => (
                                            <td key={j} className={typeof cell === "number" ? "num" : ""}>
                                                {j === 4 ? <Badge v={cell} /> : cell}
                                            </td>
                                        ))}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>

                {/* RIGHT PANEL */}
                {panel === "chat" && (
                    <div className="panel">
                        <div className="panel-head">
                            <span className="panel-title" style={{ color: "var(--secondary-11)" }}>
                                💬 Chat with table
                            </span>
                            <button className="panel-close" onClick={() => setPanel(null)}><IconClose /></button>
                        </div>
                        <div className="chat-body">
                            {messages.map((m, i) => (
                                <div key={i} className={`chat-msg ${m.role}`}>
                                    <div className="chat-bubble">{m.text}</div>
                                </div>
                            ))}
                            <div ref={chatEnd} />
                        </div>
                        <div className="chat-input-area">
                            <textarea
                                className="chat-input"
                                rows={2}
                                placeholder="Ask anything about the data…"
                                value={chatInput}
                                onChange={e => setChatInput(e.target.value)}
                                onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMsg(); } }}
                            />
                            <button className="chat-send" onClick={sendMsg}><IconSend /></button>
                        </div>
                    </div>
                )}

                {panel === "stats" && (
                    <div className="panel">
                        <div className="panel-head">
                            <span className="panel-title">📊 Quick stats</span>
                            <button className="panel-close" onClick={() => setPanel(null)}><IconClose /></button>
                        </div>
                        <div className="stats-body">
                            {/* Variety distribution */}
                            <div className="variety-dist">
                                <div className="stat-col" style={{ color: "var(--secondary-10)" }}>Variety distribution</div>
                                {[
                                    { name: "Setosa", pct: 33, fill: "var(--accent-7)" },
                                    { name: "Versicolor", pct: 33, fill: "var(--secondary-8)" },
                                    { name: "Virginica", pct: 34, fill: "var(--tertiary-7)" },
                                ].map(v => (
                                    <div key={v.name} className="variety-row">
                                        <span className="variety-label">{v.name}</span>
                                        <div className="variety-bar">
                                            <div className="variety-bar-fill" style={{ width: `${v.pct}%`, background: v.fill }} />
                                        </div>
                                        <span className="variety-pct">{v.pct}%</span>
                                    </div>
                                ))}
                            </div>

                            {/* Numeric stats */}
                            {STATS.map(s => (
                                <div key={s.col} className="stat-card">
                                    <div className="stat-col">{s.col.replace("_", " ")}</div>
                                    {[
                                        { label: "Min", val: s.min, bar: s.min / s.max, color: "var(--accent-5)" },
                                        { label: "Max", val: s.max, bar: 1, color: "var(--accent-8)" },
                                        { label: "Mean", val: s.mean, bar: s.mean / s.max, color: "var(--secondary-8)" },
                                        { label: "Std", val: s.std, bar: s.std / s.max, color: "var(--tertiary-7)" },
                                    ].map(r => (
                                        <div key={r.label} className="stat-row">
                                            <span className="stat-label">{r.label}</span>
                                            <MiniBar val={r.bar} max={1} color={r.color} />
                                            <span className="stat-val">{r.val}</span>
                                        </div>
                                    ))}
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </>
    );
}