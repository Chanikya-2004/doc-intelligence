import { useState } from "react";
import { useDropzone } from "react-dropzone";
import axios from "axios";
import { Upload, CheckCircle, Loader } from "lucide-react";
import styles from "../styles/UploadArea.module.css";

const API_BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

export default function UploadArea({ onSuccess }) {
    const [uploading, setUploading] = useState(false);
    const [uploadedFile, setUploadedFile] = useState(null);
    const [error, setError] = useState(null);

    const onDrop = async (acceptedFiles) => {
        const file = acceptedFiles[0];
        if (!file) return;
        setUploading(true);
        setError(null);
        const formData = new FormData();
        formData.append("file", file);
        try {
            const res = await axios.post(`${API_BASE}/upload`, formData, {
                headers: { "Content-Type": "multipart/form-data" },
            });
            setUploadedFile({
                filename: res.data.filename,
                chunks: res.data.pipeline_summary.chunks_created,
                vectors: res.data.pipeline_summary.vectors_stored,
            });
            setTimeout(() => onSuccess(), 500);
        } catch (err) {
            setError(err.response?.data?.detail || "Upload failed. Try again.");
        } finally {
            setUploading(false);
        }
    };

    const { getRootProps, getInputProps, isDragActive } = useDropzone({
        onDrop,
        accept: { "application/pdf": [".pdf"] },
        disabled: uploading,
    });

    if (uploadedFile) {
        return (
            <div className={styles.container}>
                <div className={styles.success}>
                    <CheckCircle size={48} color="var(--green)" />
                    <h2>Document uploaded successfully!</h2>
                    <p className={styles.filename}>{uploadedFile.filename}</p>
                    <div className={styles.stats}>
                        <div className={styles.stat}>
                            <div className={styles.statNum}>{uploadedFile.chunks}</div>
                            <div className={styles.statLabel}>Chunks created</div>
                        </div>
                        <div className={styles.stat}>
                            <div className={styles.statNum}>{uploadedFile.vectors}</div>
                            <div className={styles.statLabel}>Vectors stored</div>
                        </div>
                    </div>
                    <button className={styles.ctaBtn} onClick={() => setUploadedFile(null)}>
                        Upload another document
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className={styles.container}>
            <div {...getRootProps()} className={`${styles.dropzone} ${isDragActive ? styles.active : ""} ${uploading ? styles.disabled : ""}`}>
                <input {...getInputProps()} />
                {uploading ? (
                    <div className={styles.uploading}>
                        <Loader size={44} className={styles.spinner} />
                        <h3>Processing your document...</h3>
                        <p>Parsing, chunking, and embedding your PDF</p>
                    </div>
                ) : (
                    <div className={styles.content}>
                        <Upload size={44} color="var(--blue)" />
                        <h3>Drop your PDF here</h3>
                        <p>or click to select a file</p>
                        <span className={styles.hint}>Supports PDF files up to 50MB</span>
                    </div>
                )}
            </div>
            {error && <div className={styles.error}>{error}</div>}
        </div>
    );
}