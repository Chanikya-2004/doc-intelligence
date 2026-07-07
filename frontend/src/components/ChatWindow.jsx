import { useState, useRef, useEffect } from "react";
import axios from "axios";
import { Send, Loader } from "lucide-react";
import CitationChip from "./CitationChip";
import styles from "../styles/ChatWindow.module.css";

export default function ChatWindow({ selectedDoc, apiBase }) {
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState("");
    const [loading, setLoading] = useState(false);
    const [sessionId, setSessionId] = useState(null);
    const scrollRef = useRef(null);

    // Reset session when user switches to a different document
    useEffect(() => {
        setMessages([]);
        setSessionId(null);
    }, [selectedDoc?.filename]);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages]);

    const handleSend = async () => {
        if (!input.trim() || loading) return;
        const userMsg = input;
        setInput("");
        setMessages((prev) => [...prev, { role: "user", content: userMsg }]);
        setLoading(true);

        try {
            const res = await axios.post(`${apiBase}/chat`, {
                question: userMsg,
                n_results: 5,
                filename_filter: selectedDoc.filename,
                session_id: sessionId, // null on first message, UUID on follow-ups
            });

            // Save the session_id returned by backend so next message continues
            // the same conversation in the database
            if (res.data.session_id) {
                setSessionId(res.data.session_id);
            }

            setMessages((prev) => [
                ...prev,
                {
                    role: "assistant",
                    content: res.data.answer,
                    sources: res.data.sources || [],
                },
            ]);
        } catch (err) {
            const detail = err.response?.data?.detail || "";
            const userFriendly = detail.includes("1500")
                ? "Daily AI limit reached. Free tier allows 1500 requests/day. Try again tomorrow."
                : detail || "Something went wrong. Please try your question again.";

            setMessages((prev) => [
                ...prev,
                { role: "error", content: userFriendly },
            ]);
        } finally {
            setLoading(false);
        }
    };

    const handleKeyPress = (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    return (
        <div className={styles.window}>
            <div className={styles.header}>
                <div className={styles.docInfo}>
                    <span className={styles.docIcon}>📄</span>
                    <div>
                        <div className={styles.docName}>{selectedDoc.filename}</div>
                        <div className={styles.docMeta}>
                            {sessionId
                                ? "Conversation in progress"
                                : "Ready to answer questions about this document"}
                        </div>
                    </div>
                </div>
            </div>

            <div className={styles.messagesContainer} ref={scrollRef}>
                {messages.length === 0 && (
                    <div className={styles.emptyState}>
                        <div className={styles.welcomeIcon}>💬</div>
                        <h3>Start asking questions</h3>
                        <p>
                            I'll search through <strong>{selectedDoc.filename}</strong> and
                            give you grounded answers with citations.
                        </p>
                    </div>
                )}

                {messages.map((msg, idx) => (
                    <div key={idx} className={`${styles.message} ${styles[msg.role]}`}>
                        <div className={styles.messageContent}>
                            <div className={styles.text}>{msg.content}</div>
                            {msg.sources && msg.sources.length > 0 && (
                                <div className={styles.citationContainer}>
                                    <div className={styles.citationLabel}>Sources:</div>
                                    <div className={styles.citations}>
                                        {msg.sources.map((source, i) => (
                                            <CitationChip key={i} source={source} index={i + 1} />
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                ))}

                {loading && (
                    <div className={`${styles.message} ${styles.assistant}`}>
                        <div className={styles.messageContent}>
                            <div className={styles.typingIndicator}>
                                <span></span>
                                <span></span>
                                <span></span>
                            </div>
                        </div>
                    </div>
                )}
            </div>

            <div className={styles.inputArea}>
                <textarea
                    className={styles.input}
                    placeholder="Ask a question about your document..."
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyPress={handleKeyPress}
                    rows={1}
                    disabled={loading}
                />
                <button
                    className={styles.sendBtn}
                    onClick={handleSend}
                    disabled={!input.trim() || loading}
                >
                    {loading ? <Loader size={18} className={styles.spinner} /> : <Send size={18} />}
                </button>
            </div>
        </div>
    );
}