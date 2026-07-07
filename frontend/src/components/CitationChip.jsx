import { useState } from "react";
import { ChevronDown } from "lucide-react";
import styles from "../styles/CitationChip.module.css";

export default function CitationChip({ source, index }) {
    const [expanded, setExpanded] = useState(false);

    return (
        <div className={styles.chipWrapper}>
            <button className={styles.chip} onClick={() => setExpanded(!expanded)}>
                <span>Source {index}</span>
                <ChevronDown size={12} className={expanded ? styles.chevronOpen : ""} />
            </button>
            {expanded && (
                <div className={styles.expandedContent}>
                    <div className={styles.sourceDetails}>
                        <div className={styles.detailRow}>
                            <span className={styles.label}>File:</span>
                            <span className={styles.value}>{source.filename}</span>
                        </div>
                        <div className={styles.detailRow}>
                            <span className={styles.label}>Page:</span>
                            <span className={styles.value}>{source.page_number}</span>
                        </div>
                        <div className={styles.detailRow}>
                            <span className={styles.label}>Relevance:</span>
                            <span className={styles.value}>{(source.relevance_score * 100).toFixed(1)}%</span>
                        </div>
                    </div>
                    <div className={styles.excerpt}>
                        <div className={styles.excerptLabel}>Excerpt:</div>
                        <p>{source.excerpt}</p>
                    </div>
                </div>
            )}
        </div>
    );
}