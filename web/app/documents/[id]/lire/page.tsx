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

export default function LirePage() {
  const params = useParams();
  const documentId = params.id;
  const [document, setDocument] = useState<DocumentDetail | null>(null);
  const [error, setError] = useState("");
  const [marked, setMarked] = useState(false);

  useEffect(() => {
    apiFetch(`/documents/${documentId}`)
      .then((doc) => {
        setDocument(doc);
        // Accusé de lecture automatique à l'ouverture
        apiFetch(`/documents/${documentId}/mark-read`, { method: "POST" })
          .then(() => setMarked(true))
          .catch(() => {});
      })
      .catch((err) => setError(err.message));
  }, [documentId]);

  if (!document) return <div>Chargement...</div>;

  return (
    <>
      <AppHeader title="Lecture" />
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
          }}
        >
          {document.contenu || "(aucun contenu)"}
        </div>

        {error && <p className="error">{error}</p>}
        {marked && <p className="success" style={{ marginTop: "1rem" }}>Lecture enregistrée.</p>}
      </div>
    </>
  );
}