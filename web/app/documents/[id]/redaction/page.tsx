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

interface Template {
  id: number;
  type_document: string;
  nom: string;
  contenu_structure: string;
}

export default function RedactionPage() {
  const params = useParams();
  const documentId = params.id;

  const [document, setDocument] = useState<DocumentDetail | null>(null);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [contenu, setContenu] = useState("");
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    apiFetch(`/documents/${documentId}`)
      .then((doc: DocumentDetail) => {
        setDocument(doc);
        apiFetch("/documents/templates").then((tpls: Template[]) => {
          setTemplates(tpls);
          if (doc.contenu) {
            setContenu(doc.contenu);
          } else {
            const matching = tpls.find((t) => t.type_document === doc.type_document);
            if (matching) setContenu(matching.contenu_structure);
          }
        });
      })
      .catch((err) => setError(err.message));
  }, [documentId]);

  async function handleSave() {
    setError("");
    setSaved(false);
    try {
      await apiFetch(`/documents/${documentId}/draft`, {
        method: "PATCH",
        body: JSON.stringify({ contenu }),
      });
      setSaved(true);
    } catch (err: any) {
      setError(err.message);
    }
  }

  if (!document) return <div className="header-bar">Chargement...</div>;

  return (
    <>
      <AppHeader title="Rédaction" />
      <div className="card" style={{ maxWidth: 800 }}>
        <h2>{document.intitule}</h2>
        <p style={{ color: "#6b7280" }}>
          Type : {document.type_document} — Statut : {document.statut}
        </p>

        <div className="field">
          <label>Contenu</label>
          <textarea
            value={contenu}
            onChange={(e) => setContenu(e.target.value)}
            rows={20}
            style={{ fontFamily: "monospace" }}
          />
        </div>

        {error && <p className="error">{error}</p>}
        {saved && <p className="success">Brouillon sauvegardé.</p>}

        <button className="btn-primary" onClick={handleSave}>
          Sauvegarder le brouillon
        </button>
        <button className="btn-primary" onClick={handleSubmitReview} style={{ marginLeft: "0.75rem" }}>
         Soumettre pour vérification
        </button>
      </div>
    </>
  );
  async function handleSubmitReview() {
  setError("");
  try {
    await apiFetch(`/documents/${documentId}/submit-review`, { method: "PATCH" });
    setSaved(true);
  } catch (err: any) {
    setError(err.message);
  }
}
}