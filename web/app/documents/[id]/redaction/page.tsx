"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { apiFetch } from "@/lib/api";
import AppHeader from "@/components/AppHeader";
import { CheckCircle2 } from "lucide-react";

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

interface Signature {
  id: number;
  user_email: string;
  role_signataire: string;
  nom_signature: string;
  date: string;
}

export default function RedactionPage() {
  const params = useParams();
  const documentId = params.id;

  const [document, setDocument] = useState<DocumentDetail | null>(null);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [signatures, setSignatures] = useState<Signature[]>([]);
  const [contenu, setContenu] = useState("");
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [showSignPanel, setShowSignPanel] = useState(false);
  const [nomSignature, setNomSignature] = useState("");
  const [signPassword, setSignPassword] = useState("");
  const [certification, setCertification] = useState(false);

  function load() {
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
    apiFetch(`/documents/${documentId}/signatures`).then(setSignatures).catch(() => {});
  }

  useEffect(() => {
    load();
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

  async function handleSubmitReview() {
    setError("");
    try {
      const updated = await apiFetch(`/documents/${documentId}/submit-review`, { method: "PATCH" });
      setDocument(updated);
      setSaved(true);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function handleSign() {
    setError("");
    try {
      await apiFetch(`/documents/${documentId}/sign`, {
        method: "POST",
        body: JSON.stringify({ nom_signature: nomSignature, password: signPassword, certification }),
      });
      setSaved(true);
      setShowSignPanel(false);
      setNomSignature("");
      setSignPassword("");
      setCertification(false);
      load();
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

        {signatures.length > 0 && (
          <div style={{ marginBottom: "1.5rem" }}>
            <h3>Signatures</h3>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem", marginTop: "0.75rem" }}>
              {signatures.map((s) => (
                <div
                  key={s.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "0.5rem",
                    background: "rgba(57, 181, 74, 0.08)",
                    border: "1px solid rgba(57, 181, 74, 0.3)",
                    borderRadius: 8,
                    padding: "0.6rem 1rem",
                  }}
                >
                  <CheckCircle2 size={20} color="#00543f" />
                  <div>
                    <div className="signature-badge-name">{s.nom_signature}</div>
                    <div style={{ fontSize: "0.7rem", color: "#9ca3af" }}>
                      {s.user_email} — {s.role_signataire} — {new Date(s.date).toLocaleString()}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

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
        {saved && <p className="success">Action effectuée avec succès.</p>}

        <button className="btn-primary" onClick={handleSave}>
          Sauvegarder le brouillon
        </button>
        <button className="btn-primary" onClick={handleSubmitReview} style={{ marginLeft: "0.75rem" }}>
          Soumettre pour vérification
        </button>

        {!showSignPanel ? (
          <button className="btn-primary" onClick={() => setShowSignPanel(true)} style={{ marginLeft: "0.75rem" }}>
            Signer le document
          </button>
        ) : null}

        {showSignPanel && (
          <div className="card" style={{ marginTop: "1rem", maxWidth: 500 }}>
            <h3>Signature électronique</h3>

            <div className="field">
              <label>Tapez votre nom complet pour signer</label>
              <input value={nomSignature} onChange={(e) => setNomSignature(e.target.value)} placeholder="Prénom Nom" />
            </div>

            <div className="signature-preview">
              {nomSignature || "Votre signature apparaîtra ici"}
            </div>

            <label style={{ display: "flex", alignItems: "flex-start", gap: "0.5rem", margin: "1rem 0" }}>
              <input
                type="checkbox"
                checked={certification}
                onChange={(e) => setCertification(e.target.checked)}
                style={{ marginTop: "0.2rem" }}
              />
              <span style={{ fontSize: "0.9rem" }}>
                Je certifie avoir vérifié le contenu de ce document et j'appose ma signature
                électronique en toute connaissance de cause.
              </span>
            </label>

            <div className="field">
              <label>Confirmez votre mot de passe pour signer</label>
              <input
                type="password"
                value={signPassword}
                onChange={(e) => setSignPassword(e.target.value)}
              />
            </div>

            <div style={{ display: "flex", gap: "0.75rem" }}>
              <button
                className="btn-primary"
                onClick={handleSign}
                disabled={!nomSignature.trim() || !certification || !signPassword}
              >
                Confirmer la signature
              </button>
              <button
                className="btn-primary"
                style={{ background: "#9ca3af" }}
                onClick={() => setShowSignPanel(false)}
              >
                Annuler
              </button>
            </div>
          </div>
        )}
      </div>
    </>
  );
}