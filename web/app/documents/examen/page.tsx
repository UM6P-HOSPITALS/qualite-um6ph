"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import AppHeader from "@/components/AppHeader";

interface PendingRequest {
  id: number;
  document_id: number;
  intitule: string;
  nature: string;
  type_document: string;
  justification: string;
  demandeur_email: string;
  date: string;
}

export default function ExamenPage() {
  const [requests, setRequests] = useState<PendingRequest[]>([]);
  const [error, setError] = useState("");
  const [openId, setOpenId] = useState<number | null>(null);

  const [redacteurs, setRedacteurs] = useState("");
  const [verificateurs, setVerificateurs] = useState("");
  const [approbateurs, setApprobateurs] = useState("");
  const [perimetre, setPerimetre] = useState("");
  const [confidentialite, setConfidentialite] = useState("public");
  const [motif, setMotif] = useState("");

  function loadRequests() {
    apiFetch("/documents/requests/pending")
      .then(setRequests)
      .catch((err) => setError(err.message));
  }

  useEffect(() => {
    loadRequests();
  }, []);

  function splitEmails(value: string): string[] {
    return value
      .split(",")
      .map((e) => e.trim())
      .filter(Boolean);
  }

  async function handleAccept(requestId: number) {
    setError("");
    try {
      await apiFetch(`/documents/requests/${requestId}/accept`, {
        method: "PATCH",
        body: JSON.stringify({
          redacteur_emails: splitEmails(redacteurs),
          verificateur_emails: splitEmails(verificateurs),
          approbateur_emails: splitEmails(approbateurs),
          perimetre,
          confidentialite,
        }),
      });
      setOpenId(null);
      loadRequests();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function handleReject(requestId: number) {
    setError("");
    try {
      await apiFetch(`/documents/requests/${requestId}/reject`, {
        method: "PATCH",
        body: JSON.stringify({ motif }),
      });
      setOpenId(null);
      loadRequests();
    } catch (err: any) {
      setError(err.message);
    }
  }

  return (
    <>
      <AppHeader title="Examen des demandes" />

      <div style={{ maxWidth: 700, margin: "2rem auto" }}>
        {error && <p className="error">{error}</p>}

        {requests.length === 0 && <p>Aucune demande en attente.</p>}

        {requests.map((r) => (
          <div key={r.id} className="card" style={{ margin: "1rem auto" }}>
            <h3>{r.intitule}</h3>
            <p>
              <strong>Nature :</strong> {r.nature} — <strong>Type :</strong> {r.type_document}
            </p>
            <p>
              <strong>Demandeur :</strong> {r.demandeur_email}
            </p>
            <p>{r.justification}</p>

            {openId !== r.id ? (
              <div style={{ display: "flex", gap: "0.75rem" }}>
                <button className="btn-primary" onClick={() => setOpenId(r.id)}>
                  Examiner
                </button>
              </div>
            ) : (
              <div style={{ marginTop: "1rem" }}>
                <div className="field">
                  <label>Rédacteur(s) (emails séparés par virgule)</label>
                  <input value={redacteurs} onChange={(e) => setRedacteurs(e.target.value)} />
                </div>
                <div className="field">
                  <label>Vérificateur(s)</label>
                  <input value={verificateurs} onChange={(e) => setVerificateurs(e.target.value)} />
                </div>
                <div className="field">
                  <label>Approbateur(s) (optionnel)</label>
                  <input value={approbateurs} onChange={(e) => setApprobateurs(e.target.value)} />
                </div>
                <div className="field">
                  <label>Périmètre documentaire</label>
                  <input value={perimetre} onChange={(e) => setPerimetre(e.target.value)} />
                </div>
                <div className="field">
                  <label>Confidentialité</label>
                  <select value={confidentialite} onChange={(e) => setConfidentialite(e.target.value)}>
                    <option value="public">Public</option>
                    <option value="restreint">Restreint</option>
                    <option value="confidentiel">Confidentiel</option>
                  </select>
                </div>

                <div style={{ display: "flex", gap: "0.75rem", marginTop: "1rem" }}>
                  <button className="btn-primary" onClick={() => handleAccept(r.id)}>
                    Accepter
                  </button>
                </div>

                <hr style={{ margin: "1.5rem 0" }} />

                <div className="field">
                  <label>Motif de rejet</label>
                  <input value={motif} onChange={(e) => setMotif(e.target.value)} />
                </div>
                <button
                  className="btn-primary"
                  style={{ background: "#c0392b" }}
                  onClick={() => handleReject(r.id)}
                >
                  Rejeter
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </>
  );
}