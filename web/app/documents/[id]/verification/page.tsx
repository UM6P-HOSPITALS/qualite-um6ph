"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { apiFetch } from "@/lib/api";
import AppHeader from "@/components/AppHeader";

interface DocumentDetail {
  id: number;
  intitule: string;
  type_document: string;
  statut: string;
  contenu: string | null;
}

interface Comment {
  id: number;
  user_email: string;
  contenu: string;
  date: string;
}

export default function VerificationPage() {
  const params = useParams();
  const documentId = params.id;

  const [document, setDocument] = useState<DocumentDetail | null>(null);
  const [comments, setComments] = useState<Comment[]>([]);
  const [newComment, setNewComment] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  function load() {
    apiFetch(`/documents/${documentId}`).then(setDocument).catch((err) => setError(err.message));
    apiFetch(`/documents/${documentId}/comments`).then(setComments).catch((err) => setError(err.message));
  }

  useEffect(() => {
    load();
  }, [documentId]);

  async function handleAddComment() {
    setError("");
    try {
      await apiFetch(`/documents/${documentId}/comments`, {
        method: "POST",
        body: JSON.stringify({ contenu: newComment }),
      });
      setNewComment("");
      load();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function handleReturnToAuthor() {
    setError("");
    setMessage("");
    try {
      await apiFetch(`/documents/${documentId}/return-to-author`, { method: "PATCH" });
      setMessage("Document retourné au rédacteur.");
      load();
    } catch (err: any) {
      setError(err.message);
    }
  }

  if (!document) return <div>Chargement...</div>;

  return (
    <>
      <AppHeader title="Vérification" />
      <div className="card" style={{ maxWidth: 800 }}>
        <h2>{document.intitule}</h2>
        <p style={{ color: "#6b7280" }}>
          Type : {document.type_document} — Statut : {document.statut}
        </p>

        <div
          style={{
            background: "#f9fafb",
            border: "1px solid #e5e7eb",
            borderRadius: 8,
            padding: "1rem",
            whiteSpace: "pre-wrap",
            fontFamily: "monospace",
            marginBottom: "1.5rem",
          }}
        >
          {document.contenu || "(aucun contenu)"}
        </div>

        <h3>Commentaires</h3>
        {comments.map((c) => (
          <div key={c.id} style={{ marginBottom: "0.75rem", fontSize: "0.9rem" }}>
            <strong>{c.user_email}</strong> —{" "}
            <span style={{ color: "#9ca3af" }}>{new Date(c.date).toLocaleString()}</span>
            <p style={{ margin: "0.25rem 0" }}>{c.contenu}</p>
          </div>
        ))}

        <div className="field">
          <label>Ajouter un commentaire</label>
          <textarea value={newComment} onChange={(e) => setNewComment(e.target.value)} rows={3} />
        </div>
        <button className="btn-primary" onClick={handleAddComment} style={{ marginBottom: "1.5rem" }}>
          Commenter
        </button>

        {error && <p className="error">{error}</p>}
        {message && <p className="success">{message}</p>}

        <div>
          <button className="btn-primary" onClick={handleReturnToAuthor}>
            Retourner au rédacteur
          </button>
        </div>
      </div>
    </>
  );
}