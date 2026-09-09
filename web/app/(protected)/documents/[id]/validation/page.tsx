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

interface Validation {
  id: number;
  user_email: string;
  role_direction: string;
  nom_signature: string;
  date: string;
}

export default function ValidationPage() {
  const params = useParams();
  const documentId = params.id;

  const [document, setDocument] = useState<DocumentDetail | null>(null);
  const [validations, setValidations] = useState<Validation[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [showPanel, setShowPanel] = useState(false);
  const [nomSignature, setNomSignature] = useState("");
  const [password, setPassword] = useState("");
  const [certification, setCertification] = useState(false);

  function load() {
    apiFetch(`/documents/${documentId}`).then(setDocument).catch((err) => setError(err.message));
    apiFetch(`/documents/${documentId}/validations`).then(setValidations).catch(() => {});
  }

  useEffect(() => {
    load();
  }, [documentId]);

  async function handleValidate() {
    setError("");
    setMessage("");
    try {
      await apiFetch(`/documents/${documentId}/validate`, {
        method: "POST",
        body: JSON.stringify({ nom_signature: nomSignature, password, certification }),
      });
      setMessage("Document validé.");
      setShowPanel(false);
      setNomSignature("");
      setPassword("");
      setCertification(false);
      load();
    } catch (err: any) {
      setError(err.message);
    }
  }

  if (!document) return <div>Chargement...</div>;

  return (
    <>
      <AppHeader title="Validation" />
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

        {validations.length > 0 && (
          <div style={{ marginBottom: "1.5rem" }}>
            <h3>Validations</h3>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem", marginTop: "0.75rem" }}>
              {validations.map((v) => (
                <div
                  key={v.id}
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
                    <div className="signature-badge-name">{v.nom_signature}</div>
                    <div style={{ fontSize: "0.7rem", color: "#9ca3af" }}>
                      {v.user_email} — {v.role_direction} — {new Date(v.date).toLocaleString()}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {error && <p className="error">{error}</p>}
        {message && <p className="success">{message}</p>}

        {!showPanel ? (
          <button className="btn-primary" onClick={() => setShowPanel(true)}>
            Valider le document
          </button>
        ) : (
          <div className="card" style={{ marginTop: "1rem", maxWidth: 500 }}>
            <h3>Signature de validation</h3>
            <div className="field">
              <label>Tapez votre nom complet pour valider</label>
              <input value={nomSignature} onChange={(e) => setNomSignature(e.target.value)} placeholder="Prénom Nom" />
            </div>
            <div className="signature-preview">{nomSignature || "Votre signature apparaîtra ici"}</div>
            <label style={{ display: "flex", alignItems: "flex-start", gap: "0.5rem", margin: "1rem 0" }}>
              <input
                type="checkbox"
                checked={certification}
                onChange={(e) => setCertification(e.target.checked)}
                style={{ marginTop: "0.2rem" }}
              />
              <span style={{ fontSize: "0.9rem" }}>
                Je certifie avoir examiné ce document et j'autorise sa validation.
              </span>
            </label>
            <div className="field">
              <label>Confirmez votre mot de passe</label>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
            </div>
            <div style={{ display: "flex", gap: "0.75rem" }}>
              <button
                className="btn-primary"
                onClick={handleValidate}
                disabled={!nomSignature.trim() || !certification || !password}
              >
                Confirmer la validation
              </button>
              <button className="btn-primary" style={{ background: "#9ca3af" }} onClick={() => setShowPanel(false)}>
                Annuler
              </button>
            </div>
          </div>
        )}
      </div>
    </>
  );
}