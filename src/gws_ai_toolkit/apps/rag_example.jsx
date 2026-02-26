import { useState, useRef, useEffect } from "react";

const MOCK_SOURCES = [
    { id: 1, name: "22718743.pdf", pages: "p. 12-14", relevance: 94 },
    { id: 2, name: "22291054.pdf", pages: "p. 3-5", relevance: 87 },
    { id: 3, name: "20819283.pdf", pages: "p. 21", relevance: 76 },
    { id: 4, name: "22291053.pdf", pages: "p. 8-9", relevance: 71 },
    { id: 5, name: "22291061.pdf", pages: "p. 1-2", relevance: 65 },
];

const MOCK_MESSAGES = [
    {
        role: "user",
        content: "What is chromatography?",
    },
    {
        role: "assistant",
        content: `Chromatography is a laboratory technique used for the separation of mixtures into their individual components based on differences in how they interact with a stationary phase and a mobile phase.

In chromatography, the mixture to be separated is dissolved in a fluid (the mobile phase), which carries it through a structure holding another material (the stationary phase). The various components of the mixture move at different speeds, causing them to separate as they flow through or over the stationary phase.

There are several types of chromatography, including high-performance liquid chromatography (HPLC), gas chromatography (GC), ion chromatography, and capillary electrophoresis. Each type uses different mechanisms and phases but relies on the same fundamental principle of differential partitioning between phases to achieve separation.`,
        sources: MOCK_SOURCES,
    },
];

const SUGGESTED_QUESTIONS = [
    "Are there separation methods for ethyl sulfate?",
    "What analytical techniques detect trace impurities?",
    "Compare HPLC and GC for volatile compounds",
    "What sample preparation is needed for ion chromatography?",
];

// Icons
const SendIcon = () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <line x1="22" y1="2" x2="11" y2="13" />
        <polygon points="22 2 15 22 11 13 2 9 22 2" />
    </svg>
);

const DocIcon = () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
    </svg>
);

const PlusIcon = () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <line x1="12" y1="5" x2="12" y2="19" />
        <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
);

const HistoryIcon = () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" />
        <polyline points="12 6 12 12 16 14" />
    </svg>
);

const BookIcon = () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
        <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
    </svg>
);

const SparkleIcon = ({ size = 16 }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2l2.4 7.2L22 12l-7.6 2.8L12 22l-2.4-7.2L2 12l7.6-2.8z" />
    </svg>
);

const ChevronIcon = ({ open }) => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
        style={{ transform: open ? "rotate(180deg)" : "rotate(0deg)", transition: "transform 0.25s cubic-bezier(0.4,0,0.2,1)" }}>
        <polyline points="6 9 12 15 18 9" />
    </svg>
);

const SearchIcon = () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="11" cy="11" r="8" />
        <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
);

// Color palette
const C = {
    accent1: "#f7fdfc", accent2: "#e9f8f5", accent3: "#d3f0eb", accent4: "#bde9e1",
    accent5: "#a7e1d7", accent6: "#7cd2c4", accent7: "#50c3b0", accent8: "#25b49c",
    accent9: "#1d907d", accent10: "#166c5e", accent11: "#0e483e", accent12: "#0b362f",
    accentSurface: "#d3f0eb33",
    sec1: "#f9f8fd", sec3: "#eeebfa", sec4: "#e8e4f8", sec6: "#d1c9f1",
    sec7: "#c5bbee", sec9: "#877bb8", sec10: "#675a9d", sec11: "#584a90", sec12: "#291a67",
    tert3: "#ffd4ec", tert7: "#e176b2", tert9: "#a63b77", tert10: "#881d5a",
};

function RelevanceBadge({ value }) {
    const color = value >= 85 ? C.accent9 : value >= 70 ? C.sec9 : C.tert9;
    const bg = value >= 85 ? C.accent2 : value >= 70 ? C.sec1 : C.tert3 + "55";
    return (
        <span style={{
            fontSize: "11px", fontWeight: 700, color, background: bg,
            padding: "2px 8px", borderRadius: "20px", fontFamily: "'DM Mono', monospace", flexShrink: 0,
        }}>{value}%</span>
    );
}

function SourceCard({ source, index }) {
    const colors = [
        { bg: C.accent2, icon: C.accent9 },
        { bg: C.sec3, icon: C.sec11 },
        { bg: C.tert3, icon: C.tert9 },
    ];
    const c = colors[index % 3];
    return (
        <div style={{
            display: "flex", alignItems: "center", gap: "10px",
            padding: "10px 14px", background: "rgba(255,255,255,0.6)", borderRadius: "10px",
            cursor: "pointer", transition: "all 0.2s ease",
            border: "1px solid rgba(14, 72, 62, 0.06)",
        }}
            onMouseEnter={e => {
                e.currentTarget.style.background = "rgba(255,255,255,0.9)";
                e.currentTarget.style.borderColor = C.accent5;
                e.currentTarget.style.transform = "translateX(2px)";
            }}
            onMouseLeave={e => {
                e.currentTarget.style.background = "rgba(255,255,255,0.6)";
                e.currentTarget.style.borderColor = "rgba(14, 72, 62, 0.06)";
                e.currentTarget.style.transform = "translateX(0)";
            }}
        >
            <div style={{
                width: "32px", height: "32px", borderRadius: "8px", background: c.bg,
                display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, color: c.icon,
            }}><DocIcon /></div>
            <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{
                    fontSize: "13px", fontWeight: 600, color: C.accent12,
                    whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
                    fontFamily: "'DM Sans', sans-serif",
                }}>{source.name}</div>
                <div style={{ fontSize: "11px", color: C.accent9, fontFamily: "'DM Sans', sans-serif", opacity: 0.7 }}>{source.pages}</div>
            </div>
            <RelevanceBadge value={source.relevance} />
        </div>
    );
}

function SourcesPanel({ sources }) {
    const [open, setOpen] = useState(false);
    return (
        <div style={{
            marginTop: "14px", borderRadius: "14px",
            border: `1px solid ${C.accent3}`, overflow: "hidden",
            background: C.accent1,
        }}>
            <button onClick={() => setOpen(!open)} style={{
                width: "100%", display: "flex", alignItems: "center", justifyContent: "space-between",
                padding: "12px 16px", background: "none", border: "none", cursor: "pointer",
                fontFamily: "'DM Sans', sans-serif", fontSize: "13px", fontWeight: 600, color: C.accent11,
            }}>
                <span style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <BookIcon />
                    {sources.length} Sources Referenced
                </span>
                <ChevronIcon open={open} />
            </button>
            <div style={{
                maxHeight: open ? "400px" : "0", overflow: "hidden",
                transition: "max-height 0.35s cubic-bezier(0.4,0,0.2,1)",
            }}>
                <div style={{ padding: "2px 10px 10px", display: "flex", flexDirection: "column", gap: "5px" }}>
                    {sources.map((s, i) => <SourceCard key={s.id} source={s} index={i} />)}
                </div>
            </div>
        </div>
    );
}

function MessageBubble({ msg, isLast }) {
    const isUser = msg.role === "user";
    return (
        <div style={{
            display: "flex", flexDirection: "column",
            alignItems: isUser ? "flex-end" : "flex-start", gap: "4px",
            animation: isLast ? "fadeSlideUp 0.4s ease forwards" : "none",
            opacity: isLast ? 0 : 1, maxWidth: "100%",
        }}>
            {!isUser && (
                <div style={{ display: "flex", alignItems: "center", gap: "7px", marginBottom: "6px", marginLeft: "2px" }}>
                    <div style={{
                        width: "24px", height: "24px", borderRadius: "8px",
                        background: C.accent10,
                        display: "flex", alignItems: "center", justifyContent: "center", color: C.accent1,
                    }}><SparkleIcon size={13} /></div>
                    <span style={{
                        fontSize: "11.5px", fontWeight: 700, color: C.accent9,
                        fontFamily: "'DM Sans', sans-serif", letterSpacing: "0.04em", textTransform: "uppercase",
                    }}>AI Assistant</span>
                </div>
            )}
            <div style={{
                maxWidth: isUser ? "75%" : "100%",
                padding: isUser ? "12px 18px" : "0 2px",
                background: isUser ? C.accent11 : "transparent",
                color: isUser ? C.accent1 : C.accent12,
                borderRadius: isUser ? "20px 20px 6px 20px" : "0",
                fontSize: "15px", lineHeight: 1.75,
                fontFamily: "'Source Serif 4', Georgia, serif",
                whiteSpace: "pre-wrap", wordBreak: "break-word",
            }}>
                {msg.content}
            </div>
            {msg.sources && <SourcesPanel sources={msg.sources} />}
        </div>
    );
}

function SuggestedQuestion({ text, onClick, delay }) {
    return (
        <button onClick={onClick} style={{
            padding: "12px 16px", background: "rgba(255,255,255,0.7)",
            border: `1px solid ${C.accent3}`, borderRadius: "12px", cursor: "pointer",
            fontSize: "13.5px", color: C.accent11, fontFamily: "'DM Sans', sans-serif",
            textAlign: "left", transition: "all 0.2s ease", lineHeight: 1.45,
            animation: `fadeSlideUp 0.4s ease ${delay}ms forwards`, opacity: 0,
        }}
            onMouseEnter={e => {
                e.currentTarget.style.background = "#fff";
                e.currentTarget.style.borderColor = C.accent6;
                e.currentTarget.style.color = C.accent12;
                e.currentTarget.style.boxShadow = `0 4px 16px ${C.accent3}`;
            }}
            onMouseLeave={e => {
                e.currentTarget.style.background = "rgba(255,255,255,0.7)";
                e.currentTarget.style.borderColor = C.accent3;
                e.currentTarget.style.color = C.accent11;
                e.currentTarget.style.boxShadow = "none";
            }}
        >{text}</button>
    );
}

function EmptyState({ onSuggest }) {
    return (
        <div style={{
            display: "flex", flexDirection: "column", alignItems: "center",
            justifyContent: "center", flex: 1, gap: "36px", padding: "40px 20px",
        }}>
            <div style={{ textAlign: "center", animation: "fadeSlideUp 0.5s ease forwards", opacity: 0 }}>
                <div style={{
                    width: "72px", height: "72px", borderRadius: "22px",
                    background: C.accent10,
                    display: "flex", alignItems: "center", justifyContent: "center",
                    margin: "0 auto 22px", color: C.accent1,
                    boxShadow: `0 12px 40px ${C.accent6}88`,
                }}>
                    <SparkleIcon size={30} />
                </div>
                <h2 style={{
                    fontSize: "26px", fontWeight: 700, color: C.accent12,
                    margin: "0 0 10px", fontFamily: "'DM Sans', sans-serif", letterSpacing: "-0.02em",
                }}>Ask your documents</h2>
                <p style={{
                    fontSize: "15px", color: C.accent9, margin: 0,
                    fontFamily: "'DM Sans', sans-serif", maxWidth: "380px", lineHeight: 1.6, opacity: 0.85,
                }}>
                    Query across 20 indexed documents. Get answers with precise source citations.
                </p>
            </div>
            <div style={{
                display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px",
                width: "100%", maxWidth: "540px",
            }}>
                {SUGGESTED_QUESTIONS.map((q, i) => (
                    <SuggestedQuestion key={i} text={q} onClick={() => onSuggest(q)} delay={100 + i * 80} />
                ))}
            </div>
        </div>
    );
}

function SidebarItem({ title, date, active }) {
    return (
        <div style={{
            padding: "10px 14px", borderRadius: "10px", cursor: "pointer",
            background: active ? C.accent2 : "transparent",
            borderLeft: active ? `3px solid ${C.accent8}` : "3px solid transparent",
            transition: "all 0.15s ease",
        }}
            onMouseEnter={e => { if (!active) { e.currentTarget.style.background = C.accent1; } }}
            onMouseLeave={e => { if (!active) { e.currentTarget.style.background = "transparent"; } }}
        >
            <div style={{
                fontSize: "13.5px", fontWeight: active ? 600 : 500,
                color: active ? C.accent12 : C.accent10,
                fontFamily: "'DM Sans', sans-serif",
                whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
            }}>{title}</div>
            <div style={{
                fontSize: "11.5px", color: C.accent6,
                fontFamily: "'DM Sans', sans-serif", marginTop: "2px",
            }}>{date}</div>
        </div>
    );
}

export default function RAGChatApp() {
    const [messages, setMessages] = useState(MOCK_MESSAGES);
    const [input, setInput] = useState("");
    const [showEmpty, setShowEmpty] = useState(false);
    const [inputFocused, setInputFocused] = useState(false);
    const messagesEndRef = useRef(null);
    const inputRef = useRef(null);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    const handleSend = () => {
        if (!input.trim()) return;
        setMessages(prev => [...prev, { role: "user", content: input.trim() }]);
        setInput("");
        setShowEmpty(false);
        setTimeout(() => {
            setMessages(prev => [...prev, {
                role: "assistant",
                content: "Based on the documents in your knowledge base, I found several relevant passages addressing your question. Let me synthesize the key findings for you.\n\nThe available literature describes multiple analytical approaches that have been validated for this type of analysis. The most commonly referenced methods involve chromatographic separation followed by mass spectrometric detection.",
                sources: MOCK_SOURCES.slice(0, 3),
            }]);
        }, 1200);
    };

    const handleSuggest = (text) => {
        setInput(text);
        setShowEmpty(false);
        setTimeout(() => inputRef.current?.focus(), 50);
    };

    const handleNewChat = () => {
        setMessages([]);
        setShowEmpty(true);
    };

    return (
        <div style={{
            display: "flex", height: "100vh", width: "100vw",
            background: C.accent1, fontFamily: "'DM Sans', sans-serif", overflow: "hidden",
        }}>
            <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700&family=DM+Mono:wght@400;500&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,500;0,8..60,600;1,8..60,400&display=swap');
        @keyframes fadeSlideUp {
          from { opacity: 0; transform: translateY(12px); }
          to { opacity: 1; transform: translateY(0); }
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        ::-webkit-scrollbar { width: 5px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: ${C.accent4}; border-radius: 10px; }
        ::-webkit-scrollbar-thumb:hover { background: ${C.accent5}; }
        textarea:focus { outline: none; }
        button:focus-visible { outline: 2px solid ${C.accent7}; outline-offset: 2px; }
      `}</style>

            {/* Sidebar */}
            <div style={{
                width: "276px", background: "#fff",
                borderRight: `1px solid ${C.accent3}`,
                display: "flex", flexDirection: "column", flexShrink: 0,
            }}>
                <div style={{ padding: "20px 16px 16px" }}>
                    {/* Brand */}
                    <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "20px" }}>
                        <div style={{
                            width: "36px", height: "36px", borderRadius: "11px",
                            background: C.accent10,
                            display: "flex", alignItems: "center", justifyContent: "center", color: C.accent1,
                            boxShadow: `0 4px 12px ${C.accent6}66`,
                        }}><SparkleIcon size={17} /></div>
                        <div>
                            <div style={{ fontSize: "16px", fontWeight: 700, color: C.accent12, letterSpacing: "-0.02em" }}>DocuChat</div>
                            <div style={{ fontSize: "11.5px", color: C.accent8, fontWeight: 500 }}>20 files indexed</div>
                        </div>
                    </div>

                    {/* New Chat */}
                    <button onClick={handleNewChat} style={{
                        width: "100%", padding: "11px", display: "flex", alignItems: "center",
                        justifyContent: "center", gap: "8px",
                        background: C.accent9,
                        color: C.accent1, border: "none", borderRadius: "11px",
                        fontSize: "13.5px", fontWeight: 600, cursor: "pointer",
                        fontFamily: "'DM Sans', sans-serif", transition: "all 0.2s ease",
                        boxShadow: `0 4px 14px ${C.accent6}55`,
                    }}
                        onMouseEnter={e => { e.currentTarget.style.transform = "translateY(-1px)"; e.currentTarget.style.boxShadow = `0 6px 20px ${C.accent6}88`; }}
                        onMouseLeave={e => { e.currentTarget.style.transform = "translateY(0)"; e.currentTarget.style.boxShadow = `0 4px 14px ${C.accent6}55`; }}
                    ><PlusIcon /> New Chat</button>
                </div>

                {/* Search */}
                <div style={{ padding: "0 16px 12px" }}>
                    <div style={{
                        display: "flex", alignItems: "center", gap: "8px",
                        padding: "8px 12px", background: C.accent1, borderRadius: "9px",
                        border: `1px solid ${C.accent3}`, color: C.accent6,
                    }}>
                        <SearchIcon />
                        <span style={{ fontSize: "13px", color: C.accent5, fontFamily: "'DM Sans', sans-serif" }}>Search chats...</span>
                    </div>
                </div>

                {/* History */}
                <div style={{ padding: "0 10px", flex: 1, overflowY: "auto" }}>
                    <div style={{
                        display: "flex", alignItems: "center", gap: "6px", padding: "8px 8px 4px",
                        fontSize: "10.5px", fontWeight: 700, color: C.accent7,
                        textTransform: "uppercase", letterSpacing: "0.08em",
                    }}><HistoryIcon /> Recent</div>
                    <SidebarItem title="What is chromatography?" date="Just now" active={true} />
                    <SidebarItem title="Ethyl sulfate detection limits" date="2 hours ago" />
                    <SidebarItem title="HPLC vs GC comparison" date="Yesterday" />
                    <SidebarItem title="Sample preparation protocols" date="Yesterday" />
                    <SidebarItem title="Ion chromatography methods" date="3 days ago" />
                    <SidebarItem title="Mass spectrometry fundamentals" date="4 days ago" />
                </div>

                {/* Footer */}
                <div style={{ padding: "14px 16px", borderTop: `1px solid ${C.accent3}` }}>
                    <div style={{
                        display: "flex", alignItems: "center", gap: "10px",
                        padding: "10px 14px", background: C.accent2, borderRadius: "10px",
                        cursor: "pointer", transition: "all 0.15s ease",
                    }}
                        onMouseEnter={e => e.currentTarget.style.background = C.accent3}
                        onMouseLeave={e => e.currentTarget.style.background = C.accent2}
                    >
                        <span style={{ color: C.accent9 }}><BookIcon /></span>
                        <span style={{ fontSize: "13px", fontWeight: 600, color: C.accent11, flex: 1 }}>Knowledge Base</span>
                        <span style={{
                            fontSize: "11px", fontWeight: 700, color: C.accent9,
                            background: C.accent3, padding: "2px 9px", borderRadius: "20px",
                            fontFamily: "'DM Mono', monospace",
                        }}>20</span>
                    </div>
                </div>
            </div>

            {/* Main */}
            <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
                {/* Top bar */}
                <div style={{
                    padding: "13px 28px", display: "flex", alignItems: "center", justifyContent: "space-between",
                    borderBottom: `1px solid ${C.accent3}`,
                    background: "rgba(255,255,255,0.75)", backdropFilter: "blur(12px)", flexShrink: 0,
                }}>
                    <div style={{ fontSize: "15px", fontWeight: 600, color: C.accent12 }}>
                        {messages.length > 0 ? messages[0].content.slice(0, 50) + (messages[0].content.length > 50 ? "..." : "") : "New Chat"}
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                            <div style={{
                                width: "7px", height: "7px", borderRadius: "50%", background: C.accent7,
                                boxShadow: `0 0 6px ${C.accent7}88`,
                            }} />
                            <span style={{ fontSize: "12px", color: C.accent9, fontWeight: 500 }}>Ready</span>
                        </div>
                        {/* AI Expert tab */}
                        <div style={{
                            display: "flex", alignItems: "center", gap: "6px",
                            padding: "5px 12px", borderRadius: "8px",
                            background: C.sec3, cursor: "pointer", transition: "all 0.15s ease",
                        }}
                            onMouseEnter={e => e.currentTarget.style.background = C.sec4}
                            onMouseLeave={e => e.currentTarget.style.background = C.sec3}
                        >
                            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke={C.sec11} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <circle cx="12" cy="12" r="3" />
                                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
                            </svg>
                            <span style={{ fontSize: "12px", fontWeight: 600, color: C.sec11, fontFamily: "'DM Sans', sans-serif" }}>AI Expert</span>
                        </div>
                    </div>
                </div>

                {/* Messages */}
                <div style={{ flex: 1, overflowY: "auto", padding: "28px 28px 0" }}>
                    <div style={{
                        maxWidth: "720px", margin: "0 auto",
                        display: "flex", flexDirection: "column", minHeight: "100%",
                    }}>
                        {messages.length === 0 || showEmpty ? (
                            <EmptyState onSuggest={handleSuggest} />
                        ) : (
                            <div style={{ display: "flex", flexDirection: "column", gap: "30px", paddingBottom: "28px" }}>
                                {messages.map((msg, i) => (
                                    <MessageBubble key={i} msg={msg} isLast={i === messages.length - 1} />
                                ))}
                                <div ref={messagesEndRef} />
                            </div>
                        )}
                    </div>
                </div>

                {/* Input */}
                <div style={{
                    padding: "16px 28px 26px", flexShrink: 0,
                    background: `linear-gradient(180deg, transparent 0%, ${C.accent1} 30%)`,
                }}>
                    <div style={{ maxWidth: "720px", margin: "0 auto" }}>
                        <div style={{
                            display: "flex", alignItems: "flex-end", gap: "12px",
                            background: "#fff", borderRadius: "16px",
                            border: `1.5px solid ${inputFocused ? C.accent6 : C.accent3}`,
                            padding: "6px 6px 6px 18px",
                            boxShadow: inputFocused
                                ? `0 4px 24px ${C.accent4}, 0 0 0 3px ${C.accent2}`
                                : `0 2px 12px ${C.accent3}44`,
                            transition: "all 0.25s cubic-bezier(0.4,0,0.2,1)",
                        }}>
                            <textarea
                                ref={inputRef}
                                value={input}
                                onChange={e => setInput(e.target.value)}
                                onFocus={() => setInputFocused(true)}
                                onBlur={() => setInputFocused(false)}
                                onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
                                placeholder="Ask a question about your documents..."
                                rows={1}
                                style={{
                                    flex: 1, border: "none", background: "none",
                                    fontSize: "15px", fontFamily: "'DM Sans', sans-serif", color: C.accent12,
                                    resize: "none", padding: "10px 0", lineHeight: 1.5,
                                    maxHeight: "120px", overflowY: "auto",
                                }}
                            />
                            <button
                                onClick={handleSend}
                                disabled={!input.trim()}
                                style={{
                                    width: "42px", height: "42px", borderRadius: "12px", border: "none",
                                    background: input.trim()
                                        ? C.accent9
                                        : C.accent2,
                                    color: input.trim() ? C.accent1 : C.accent5,
                                    cursor: input.trim() ? "pointer" : "default",
                                    display: "flex", alignItems: "center", justifyContent: "center",
                                    transition: "all 0.2s ease", flexShrink: 0,
                                    boxShadow: input.trim() ? `0 3px 10px ${C.accent6}66` : "none",
                                }}
                            ><SendIcon /></button>
                        </div>
                        <div style={{
                            textAlign: "center", fontSize: "11.5px", color: C.accent6,
                            marginTop: "10px", fontFamily: "'DM Sans', sans-serif",
                        }}>
                            Answers are generated from your document library. Always verify critical information.
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}