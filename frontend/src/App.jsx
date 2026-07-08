import { useState, useEffect } from "react";
import axios from "axios";
import DocumentSidebar from "./components/DocumentSidebar";
import UploadArea from "./components/UploadArea";
import ChatWindow from "./components/ChatWindow";
import styles from "./styles/App.module.css";

const API_BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

export default function App() {
  const [documents, setDocuments] = useState([]);
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    fetchDocuments();
  }, [refreshKey]);

  const fetchDocuments = async () => {
    try {
      const res = await axios.get(`${API_BASE}/documents`);
      setDocuments(res.data.documents || []);
    } catch (err) {
      console.error("Failed to fetch documents:", err);
    }
  };

  const handleUploadSuccess = () => setRefreshKey((k) => k + 1);

  const handleDeleteDoc = (filename) => {
    setDocuments(documents.filter((d) => d.filename !== filename));
    if (selectedDoc?.filename === filename) setSelectedDoc(null);
  };

  return (
    <div className={styles.app}>
      <div className={styles.container}>
        <DocumentSidebar
          documents={documents}
          selectedDoc={selectedDoc}
          onSelectDoc={setSelectedDoc}
          onDelete={handleDeleteDoc}
          onRefresh={fetchDocuments}
        />
        <div className={styles.mainArea}>
          {!selectedDoc ? (
            <UploadArea onSuccess={handleUploadSuccess} />
          ) : (
            <ChatWindow selectedDoc={selectedDoc} apiBase={API_BASE} />
          )}
        </div>
      </div>
    </div>
  );
}