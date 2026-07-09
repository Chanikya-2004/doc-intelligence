import { useState } from "react";
import axios from "axios";
import { Trash2, FileText } from "lucide-react";
import styles from "../styles/DocumentSidebar.module.css";

const API_BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

export default function DocumentSidebar({ documents, selectedDoc, onSelectDoc, onDelete, onRefresh }) {
    const [deleting, setDeleting] = useState(null);

    const handleDelete = async (e, filename) => {
        e.stopPropagation();
        const confirmed = window.confirm(
            `Delete "${filename}"?\n\nThis will remove the document and all its stored vectors. This cannot be undone.`
        );
        if (!confirmed) return;
        setDeleting(filename);
        try {
            await axios.delete(`${API_BASE}/documents/${filename}`);
            onDelete(filename);
            onRefresh();
        } catch (err) {
            console.error("Delete failed:", err);
            alert("Delete failed. Please try again.");
        } finally {
            setDeleting(null);
        }
    };

    return (
        <div className={styles.sidebar}>
            <div className={styles.header}>
                <div className={styles.logo}>📄</div>
                <div className={styles.title}>Your Documents</div>
            </div>
            <div className={styles.docList}>
                {documents.length === 0 ? (
                    <div className={styles.empty}>
                        <FileText size={32} strokeWidth={1} />
                        <p>No documents yet</p>
                        <span>Upload a PDF to get started</span>
                    </div>
                ) : (
                    documents.map((doc) => (
                        <div
                            key={doc.filename}
                            className={`${styles.docItem} ${selectedDoc?.filename === doc.filename ? styles.selected : ""}`}
                            onClick={() => onSelectDoc(doc)}
                        >
                            <div className={styles.docName}>{doc.filename}</div>
                            <button className={styles.deleteBtn} onClick={(e) => handleDelete(e, doc.filename)} disabled={deleting === doc.filename}>
                                <Trash2 size={14} />
                            </button>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}