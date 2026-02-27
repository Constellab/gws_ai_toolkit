import { useState, useRef, useEffect } from "react";

// Color palette
const C = {
    accent1: "#f7fdfc", accent2: "#e9f8f5", accent3: "#d3f0eb", accent4: "#bde9e1",
    accent5: "#a7e1d7", accent6: "#7cd2c4", accent7: "#50c3b0", accent8: "#25b49c",
    accent9: "#1d907d", accent10: "#166c5e", accent11: "#0e483e", accent12: "#0b362f",
    sec1: "#f9f8fd", sec3: "#eeebfa", sec4: "#e8e4f8", sec5: "#dcd6f5", sec6: "#d1c9f1",
    sec7: "#c5bbee", sec9: "#877bb8", sec10: "#675a9d", sec11: "#584a90", sec12: "#291a67",
    tert3: "#ffd4ec", tert9: "#a63b77",
};

const MOCK_MESSAGES = [
    { role: "user", content: "How to run a scenario?" },
    {
        role: "assistant",
        content: `To run a scenario, follow these steps:

First, navigate to the Scenarios panel from the main dashboard. You'll find the "Run" button in the top-right corner of the scenario editor.

Before executing, make sure all required parameters are configured. The system will validate your inputs and highlight any missing fields. Once validation passes, click "Run Scenario" to begin execution.

You can monitor progress in real-time through the execution log panel, which shows each step's status, timing, and any warnings or errors encountered.`,
        sections: [
            { title: "Configuration", page: "Section 3.2" },
            { title: "Execution", page: "Section 4.1" },
            { title: "Monitoring", page: "Section 4.3" },
        ],
    },
];

const MOCK_HISTORY = [
    { id: 1, title: "How to run a scenario?", time: "32 min ago", type: "RAG", active: true },
    { id: 2, title: "How to run a scenario?", time: "2 days ago", type: "RAG" },
    { id: 3, title: "How to run a scenario?", time: "3 months ago", type: "RAG" },
    { id: 4, title: "How to run a scenario? And How can I sy...", time: "3 months ago", type: "RAG" },
    { id: 5, title: "One week before tumor cells engraftment,...", time: "3 months ago", type: "RAG" },
    { id: 6, title: "One week before tumor cells engraftment,...", time: "3 months ago", type: "RAG" },
    { id: 7, title: "Mouse health will be checked daily. A cl...", time: "3 months ago", type: "RAG" },
];

const DOC_INFO = {
    name: "scenario1_1.md",
    size: "24.3 KB",
    pages: "~12 sections",
    lastModified: "Feb 14, 2026",
};

// Icons
const SendIcon = () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" />
    </svg>
);

const DocIcon = ({ size = 16 }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" />
    </svg>
);

const PlusIcon = () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
    </svg>
);

const HistoryIcon = () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" />
    </svg>
);

const SearchIcon = () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
);

const EyeIcon = () => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" />
    </svg>
);

const ExpertIcon = ({ size = 16 }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
    </svg>
);

const ChevronIcon = ({ open }) => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
        style={{ transform: open ? "rotate(180deg)" : "rotate(0deg)", transition: "transform 0.25s cubic-bezier(0.4,0,0.2,1)" }}>
        <polyline points="6 9 12 15 18 9" />
    </svg>
);

const SectionIcon = () => (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M4 6h16M4 12h16M4 18h7" />
    </svg>
);

const SparkleIcon = ({ size = 16 }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2l2.4 7.2L22 12l-7.6 2.8L12 22l-2.4-7.2L2 12l7.6-2.8z" />
    </svg>
);

// Sidebar history item
function SidebarItem({ item }) {
    const typeColors = {
        RAG: { bg: C.accent2, color: C.accent9, border: C.accent4 },
        ai_expert: { bg: C.sec3, color: C.sec11, border: C.sec5 },
    };
    const tc = typeColors[item.type] || typeColors.RAG;

    return (
        <div style={{
            padding: "10px 12px", borderRadius: "10px", cursor: "pointer",
            background: item.active ? C.sec3 : "transparent",
            borderLeft: item.active ? `3px solid ${C.sec9}` : "3px solid transparent",
            transition: "all 0.15s ease", marginBottom: "2px",
        }}
            onMouseEnter={e => { if (!item.active) e.currentTarget.style.background = C.accent1; }}
            onMouseLeave={e => { if (!item.active) e.currentTarget.style.background = "transparent"; }}
        >
            <div style={{
                fontSize: "13px", fontWeight: item.active ? 600 : 500,
                color: item.active ? C.sec12 : C.accent11,
                fontFamily: "'DM Sans', sans-serif",
                whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
                lineHeight: 1.4,
            }}>{item.title}</div>
            <div style={{
                display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: "4px",
            }}>
                <span style={{
                    fontSize: "11px", color: C.accent6, fontFamily: "'DM Sans', sans-serif",
                }}>{item.time}</span>
                <span style={{
                    fontSize: "10px", fontWeight: 700, color: tc.color, background: tc.bg,
                    padding: "1px 7px", borderRadius: "4px", fontFamily: "'DM Mono', monospace",
                    letterSpacing: "0.03em", textTransform: "uppercase",
                }}>{item.type === "ai_expert" ? "Expert" : item.type}</span>
            </div>
        </div>
    );
}

// Document section reference in AI response
function SectionRef({ section }) {
    return (
        <div style={{
            display: "inline-flex", alignItems: "center", gap: "6px",
            padding: "4px 10px", background: C.sec1, border: `1px solid ${C.sec5}`,
            borderRadius: "7px", cursor: "pointer", transition: "all 0.15s ease",
            marginRight: "6px", marginBottom: "6px",
        }}
            onMouseEnter={e => { e.currentTarget.style.background = C.sec3; e.currentTarget.style.borderColor = C.sec7; }}
            onMouseLeave={e => { e.currentTarget.style.background = C.sec1; e.currentTarget.style.borderColor = C.sec5; }}
        >
            <SectionIcon />
            <span style={{ fontSize: "12px", fontWeight: 600, color: C.sec11, fontFamily: "'DM Sans', sans-serif" }}>
                {section.title}
            </span>
            <span style={{ fontSize: "11px", color: C.sec9, fontFamily: "'DM Mono', monospace" }}>
                {section.page}
            </span>
        </div>
    );
}

// Message bubble
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
                        background: `linear-gradient(135deg, ${C.sec9} 0%, ${C.sec12} 100%)`,
                        display: "flex", alignItems: "center", justifyContent: "center", color: "#fff",
                    }}><ExpertIcon size={13} /></div>
                    <span style={{
                        fontSize: "11.5px", fontWeight: 700, color: C.sec9,
                        fontFamily: "'DM Sans', sans-serif", letterSpacing: "0.04em", textTransform: "uppercase",
                    }}>AI Expert</span>
                </div>
            )}
            <div style={{
                maxWidth: isUser ? "75%" : "100%",
                padding: isUser ? "12px 18px" : "0 2px",
                background: isUser ? `linear-gradient(135deg, ${C.sec11} 0%, ${C.sec12} 100%)` : "transparent",
                color: isUser ? "#f9f8fd" : C.accent12,
                borderRadius: isUser ? "20px 20px 6px 20px" : "0",
                fontSize: "15px", lineHeight: 1.75,
                fontFamily: "'Source Serif 4', Georgia, serif",
                whiteSpace: "pre-wrap", wordBreak: "break-word",
            }}>
                {msg.content}
            </div>
            {msg.sections && (
                <div style={{ marginTop: "10px", display: "flex", flexWrap: "wrap" }}>
                    {msg.sections.map((s, i) => <SectionRef key={i} section={s} />)}
                </div>
            )}
        </div>
    );
}

// Suggested questions for empty state
const EXPERT_SUGGESTIONS = [
    "Summarize this document",
    "What are the key findings?",
    "List all procedures described",
    "What parameters are configurable?",
];

function EmptyState({ docName, onSuggest }) {
    return (
        <div style={{
            display: "flex", flexDirection: "column", alignItems: "center",
            justifyContent: "center", flex: 1, gap: "32px", padding: "40px 20px",
        }}>
            <div style={{ textAlign: "center", animation: "fadeSlideUp 0.5s ease forwards", opacity: 0 }}>
                {/* Document visual */}
                <div style={{
                    position: "relative", width: "80px", height: "96px", margin: "0 auto 24px",
                }}>
                    <div style={{
                        width: "72px", height: "90px", borderRadius: "12px",
                        background: `linear-gradient(160deg, ${C.sec3} 0%, ${C.sec5} 100%)`,
                        border: `1.5px solid ${C.sec6}`,
                        position: "absolute", left: "0", top: "0",
                        display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
                        gap: "5px", padding: "12px",
                    }}>
                        <div style={{ width: "32px", height: "3px", borderRadius: "2px", background: C.sec7 }} />
                        <div style={{ width: "38px", height: "3px", borderRadius: "2px", background: C.sec7 }} />
                        <div style={{ width: "28px", height: "3px", borderRadius: "2px", background: C.sec7 }} />
                        <div style={{ width: "34px", height: "3px", borderRadius: "2px", background: C.sec7 }} />
                        <div style={{ width: "20px", height: "3px", borderRadius: "2px", background: C.sec7 }} />
                    </div>
                    {/* Expert badge */}
                    <div style={{
                        position: "absolute", right: "-4px", bottom: "-4px",
                        width: "32px", height: "32px", borderRadius: "10px",
                        background: `linear-gradient(135deg, ${C.sec9} 0%, ${C.sec12} 100%)`,
                        display: "flex", alignItems: "center", justifyContent: "center", color: "#fff",
                        boxShadow: `0 4px 12px ${C.sec7}`,
                        border: "2.5px solid #fff",
                    }}>
                        <ExpertIcon size={15} />
                    </div>
                </div>

                <h2 style={{
                    fontSize: "22px", fontWeight: 700, color: C.accent12,
                    margin: "0 0 6px", fontFamily: "'DM Sans', sans-serif", letterSpacing: "-0.02em",
                }}>Full document context loaded</h2>
                <p style={{
                    fontSize: "14.5px", color: C.accent9, margin: "0 0 4px",
                    fontFamily: "'DM Sans', sans-serif", lineHeight: 1.6,
                }}>
                    Ask anything about <span style={{ fontWeight: 600, color: C.sec11 }}>{docName}</span>
                </p>
                <p style={{
                    fontSize: "13px", color: C.accent6, margin: 0,
                    fontFamily: "'DM Sans', sans-serif",
                }}>
                    The AI has read the entire document and can answer detailed questions.
                </p>
            </div>
            <div style={{
                display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px",
                width: "100%", maxWidth: "480px",
            }}>
                {EXPERT_SUGGESTIONS.map((q, i) => (
                    <button key={i} onClick={() => onSuggest(q)} style={{
                        padding: "11px 16px", background: "rgba(255,255,255,0.7)",
                        border: `1px solid ${C.sec5}`, borderRadius: "12px", cursor: "pointer",
                        fontSize: "13.5px", color: C.sec11, fontFamily: "'DM Sans', sans-serif",
                        textAlign: "left", transition: "all 0.2s ease", lineHeight: 1.4,
                        animation: `fadeSlideUp 0.4s ease ${120 + i * 70}ms forwards`, opacity: 0,
                    }}
                        onMouseEnter={e => {
                            e.currentTarget.style.background = "#fff";
                            e.currentTarget.style.borderColor = C.sec7;
                            e.currentTarget.style.boxShadow = `0 4px 16px ${C.sec5}`;
                        }}
                        onMouseLeave={e => {
                            e.currentTarget.style.background = "rgba(255,255,255,0.7)";
                            e.currentTarget.style.borderColor = C.sec5;
                            e.currentTarget.style.boxShadow = "none";
                        }}
                    >{q}</button>
                ))}
            </div>
        </div>
    );
}

export default function AIExpertPage() {
    const [messages, setMessages] = useState(MOCK_MESSAGES);
    const [input, setInput] = useState("");
    const [showEmpty, setShowEmpty] = useState(false);
    const [inputFocused, setInputFocused] = useState(false);
    const [docPanelOpen, setDocPanelOpen] = useState(false);
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
                content: "Based on the full document context, here's what I found relevant to your question.\n\nThe document describes a comprehensive approach that covers multiple aspects of the workflow. Key details are outlined across several sections with specific parameters and configurations.",
                sections: [
                    { title: "Overview", page: "Section 1.1" },
                    { title: "Parameters", page: "Section 2.4" },
                ],
            }]);
        }, 1000);
    };

    const handleSuggest = (text) => {
        setInput(text);
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
        @keyframes fadeSlideUp { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes pulse { 0%,100% { opacity:0.6; } 50% { opacity:1; } }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        ::-webkit-scrollbar { width: 5px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: ${C.accent4}; border-radius: 10px; }
        textarea:focus { outline: none; }
      `}</style>

            {/* Sidebar */}
            <div style={{
                width: "276px", background: "#fff",
                borderRight: `1px solid ${C.accent3}`,
                display: "flex", flexDirection: "column", flexShrink: 0,
            }}>
                {/* Brand */}
                <div style={{ padding: "20px 16px 16px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "20px" }}>
                        <div style={{
                            width: "36px", height: "36px", borderRadius: "11px",
                            background: `linear-gradient(135deg, ${C.accent8} 0%, ${C.accent11} 100%)`,
                            display: "flex", alignItems: "center", justifyContent: "center", color: C.accent1,
                            boxShadow: `0 4px 12px ${C.accent6}66`,
                        }}><SparkleIcon size={17} /></div>
                        <div>
                            <div style={{ fontSize: "16px", fontWeight: 700, color: C.accent12, letterSpacing: "-0.02em" }}>DocuChat</div>
                            <div style={{ fontSize: "11.5px", color: C.accent8, fontWeight: 500 }}>20 files indexed</div>
                        </div>
                    </div>

                    <button onClick={handleNewChat} style={{
                        width: "100%", padding: "11px", display: "flex", alignItems: "center",
                        justifyContent: "center", gap: "8px",
                        background: `linear-gradient(135deg, ${C.sec9} 0%, ${C.sec12} 100%)`,
                        color: "#fff", border: "none", borderRadius: "11px",
                        fontSize: "13.5px", fontWeight: 600, cursor: "pointer",
                        fontFamily: "'DM Sans', sans-serif", transition: "all 0.2s ease",
                        boxShadow: `0 4px 14px ${C.sec7}`,
                    }}
                        onMouseEnter={e => { e.currentTarget.style.transform = "translateY(-1px)"; e.currentTarget.style.boxShadow = `0 6px 20px ${C.sec7}`; }}
                        onMouseLeave={e => { e.currentTarget.style.transform = "translateY(0)"; e.currentTarget.style.boxShadow = `0 4px 14px ${C.sec7}`; }}
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
                        display: "flex", alignItems: "center", gap: "6px", padding: "8px 6px 6px",
                        fontSize: "10.5px", fontWeight: 700, color: C.accent7,
                        textTransform: "uppercase", letterSpacing: "0.08em",
                    }}><HistoryIcon /> Recent</div>
                    {MOCK_HISTORY.map(item => <SidebarItem key={item.id} item={item} />)}
                </div>

                {/* Mode switcher at bottom */}
                <div style={{ padding: "14px 16px", borderTop: `1px solid ${C.accent3}` }}>
                    <div style={{
                        display: "flex", borderRadius: "10px", overflow: "hidden",
                        border: `1px solid ${C.accent3}`, background: C.accent1,
                    }}>
                        <div style={{
                            flex: 1, padding: "9px", textAlign: "center", fontSize: "12.5px",
                            fontWeight: 500, color: C.accent9, cursor: "pointer",
                            fontFamily: "'DM Sans', sans-serif", transition: "all 0.15s ease",
                        }}
                            onMouseEnter={e => e.currentTarget.style.background = C.accent2}
                            onMouseLeave={e => e.currentTarget.style.background = "transparent"}
                        >Chat</div>
                        <div style={{
                            flex: 1, padding: "9px", textAlign: "center", fontSize: "12.5px",
                            fontWeight: 700, color: "#fff", cursor: "pointer",
                            fontFamily: "'DM Sans', sans-serif",
                            background: `linear-gradient(135deg, ${C.sec9} 0%, ${C.sec11} 100%)`,
                        }}>AI Expert</div>
                    </div>
                </div>
            </div>

            {/* Main content */}
            <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>

                {/* Top bar - Document header */}
                <div style={{
                    padding: "0 28px", display: "flex", alignItems: "center", justifyContent: "space-between",
                    borderBottom: `1px solid ${C.accent3}`,
                    background: "rgba(255,255,255,0.8)", backdropFilter: "blur(12px)", flexShrink: 0,
                    minHeight: "62px",
                }}>
                    {/* Left: Mode + Document info */}
                    <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
                        {/* Expert badge */}
                        <div style={{
                            display: "flex", alignItems: "center", gap: "7px",
                            padding: "5px 12px 5px 8px", borderRadius: "8px",
                            background: `linear-gradient(135deg, ${C.sec3}, ${C.sec4})`,
                            border: `1px solid ${C.sec6}`,
                        }}>
                            <div style={{
                                width: "22px", height: "22px", borderRadius: "6px",
                                background: `linear-gradient(135deg, ${C.sec9}, ${C.sec12})`,
                                display: "flex", alignItems: "center", justifyContent: "center", color: "#fff",
                            }}><ExpertIcon size={12} /></div>
                            <span style={{
                                fontSize: "12.5px", fontWeight: 700, color: C.sec11,
                                fontFamily: "'DM Sans', sans-serif",
                            }}>AI Expert</span>
                        </div>

                        {/* Divider */}
                        <div style={{ width: "1px", height: "28px", background: C.accent3 }} />

                        {/* Document info */}
                        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                            <div style={{
                                width: "34px", height: "34px", borderRadius: "9px",
                                background: C.sec1, border: `1px solid ${C.sec5}`,
                                display: "flex", alignItems: "center", justifyContent: "center", color: C.sec9,
                            }}><DocIcon size={17} /></div>
                            <div>
                                <div style={{
                                    fontSize: "14.5px", fontWeight: 700, color: C.accent12,
                                    fontFamily: "'DM Sans', sans-serif", letterSpacing: "-0.01em",
                                }}>{DOC_INFO.name}</div>
                                <div style={{
                                    fontSize: "11.5px", color: C.accent6,
                                    fontFamily: "'DM Sans', sans-serif",
                                }}>{DOC_INFO.size} · {DOC_INFO.pages}</div>
                            </div>
                        </div>
                    </div>

                    {/* Right: Actions */}
                    <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                        {/* Full context indicator */}
                        <div style={{
                            display: "flex", alignItems: "center", gap: "6px",
                            padding: "5px 11px", borderRadius: "8px",
                            background: C.accent2, border: `1px solid ${C.accent4}`,
                        }}>
                            <div style={{
                                width: "7px", height: "7px", borderRadius: "50%",
                                background: C.accent7, boxShadow: `0 0 6px ${C.accent7}88`,
                                animation: "pulse 2s ease infinite",
                            }} />
                            <span style={{
                                fontSize: "12px", fontWeight: 600, color: C.accent9,
                                fontFamily: "'DM Sans', sans-serif",
                            }}>Full context</span>
                        </div>

                        {/* View Document */}
                        <button onClick={() => setDocPanelOpen(!docPanelOpen)} style={{
                            display: "flex", alignItems: "center", gap: "7px",
                            padding: "8px 14px", borderRadius: "9px",
                            background: "#fff", border: `1.5px solid ${C.sec6}`,
                            cursor: "pointer", fontSize: "13px", fontWeight: 600,
                            color: C.sec11, fontFamily: "'DM Sans', sans-serif",
                            transition: "all 0.15s ease",
                        }}
                            onMouseEnter={e => { e.currentTarget.style.background = C.sec1; e.currentTarget.style.borderColor = C.sec7; }}
                            onMouseLeave={e => { e.currentTarget.style.background = "#fff"; e.currentTarget.style.borderColor = C.sec6; }}
                        >
                            <EyeIcon /> View document
                        </button>

                        {/* New chat */}
                        <button onClick={handleNewChat} style={{
                            display: "flex", alignItems: "center", gap: "6px",
                            padding: "8px 14px", borderRadius: "9px",
                            background: "#fff", border: `1.5px solid ${C.accent4}`,
                            cursor: "pointer", fontSize: "13px", fontWeight: 600,
                            color: C.accent11, fontFamily: "'DM Sans', sans-serif",
                            transition: "all 0.15s ease",
                        }}
                            onMouseEnter={e => { e.currentTarget.style.background = C.accent2; e.currentTarget.style.borderColor = C.accent5; }}
                            onMouseLeave={e => { e.currentTarget.style.background = "#fff"; e.currentTarget.style.borderColor = C.accent4; }}
                        >
                            <PlusIcon /> New chat
                        </button>
                    </div>
                </div>

                {/* Messages area */}
                <div style={{ flex: 1, overflowY: "auto", padding: "28px 28px 0" }}>
                    <div style={{
                        maxWidth: "720px", margin: "0 auto",
                        display: "flex", flexDirection: "column", minHeight: "100%",
                    }}>
                        {messages.length === 0 || showEmpty ? (
                            <EmptyState docName={DOC_INFO.name} onSuggest={handleSuggest} />
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

                {/* Input area */}
                <div style={{
                    padding: "16px 28px 26px", flexShrink: 0,
                    background: `linear-gradient(180deg, transparent 0%, ${C.accent1} 30%)`,
                }}>
                    <div style={{ maxWidth: "720px", margin: "0 auto" }}>
                        <div style={{
                            display: "flex", alignItems: "flex-end", gap: "12px",
                            background: "#fff", borderRadius: "16px",
                            border: `1.5px solid ${inputFocused ? C.sec7 : C.accent3}`,
                            padding: "6px 6px 6px 18px",
                            boxShadow: inputFocused
                                ? `0 4px 24px ${C.sec5}, 0 0 0 3px ${C.sec3}`
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
                                placeholder={`Ask about ${DOC_INFO.name}...`}
                                rows={1}
                                style={{
                                    flex: 1, border: "none", background: "none",
                                    fontSize: "15px", fontFamily: "'DM Sans', sans-serif", color: C.accent12,
                                    resize: "none", padding: "10px 0", lineHeight: 1.5,
                                    maxHeight: "120px", overflowY: "auto",
                                }}
                            />
                            <button onClick={handleSend} disabled={!input.trim()} style={{
                                width: "42px", height: "42px", borderRadius: "12px", border: "none",
                                background: input.trim()
                                    ? `linear-gradient(135deg, ${C.sec9} 0%, ${C.sec12} 100%)`
                                    : C.accent2,
                                color: input.trim() ? "#fff" : C.accent5,
                                cursor: input.trim() ? "pointer" : "default",
                                display: "flex", alignItems: "center", justifyContent: "center",
                                transition: "all 0.2s ease", flexShrink: 0,
                                boxShadow: input.trim() ? `0 3px 10px ${C.sec7}` : "none",
                            }}><SendIcon /></button>
                        </div>
                        <div style={{
                            textAlign: "center", fontSize: "11.5px", color: C.accent6,
                            marginTop: "10px", fontFamily: "'DM Sans', sans-serif",
                        }}>
                            AI Expert mode — full document context loaded for <span style={{ color: C.sec9, fontWeight: 600 }}>{DOC_INFO.name}</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}