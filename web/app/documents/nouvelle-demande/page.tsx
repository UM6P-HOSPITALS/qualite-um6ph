"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import AppHeader from "@/components/AppHeader";

interface Service {
  id: number;
  nom: string;
}

export default function NouvelleDemandePage() {
  const [services, setServices] = useState<Service[]>([]);
  const [intitule, setIntitule] = useState("");
  const [nature, setNature] = useState("creation");
  const [typeDocument, setTypeDocument] = useState("procedure");
  const [justification, setJustification] = useState("");
  const [serviceId, setServiceId] = useState<number | "">("");
  const [responsableEmail, setResponsableEmail] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    apiFetch("/documents/services")
      .then(setServices)
      .catch((err) => setError(err.message));
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSuccess(false);
    try {
      await apiFetch("/documents/requests", {
        method: "POST",
        body: JSON.stringify({
          intitule,
          nature,
          type_document: typeDocument,
          justification,
          service_id: Number(serviceId),
          responsable_email: responsableEmail,
        }),
      });
      setSuccess(true);
      setIntitule("");
      setJustification("");
      setResponsableEmail("");
    } catch (err: any) {
      setError(err.message);
    }
  }

  return (
    <>
      <AppHeader title="Nouvelle demande" />

      <form className="card" onSubmit={handleSubmit}>
        <h2>Nouvelle demande de document</h2>

        <div className="field">
          <label>Intitulé du document</label>
          <input
            value={intitule}
            onChange={(e) => setIntitule(e.target.value)}
            required
          />
        </div>

        <div className="field">
          <label>Nature de la demande</label>
          <select value={nature} onChange={(e) => setNature(e.target.value)}>
            <option value="creation">Création</option>
            <option value="modification">Modification</option>
          </select>
        </div>

        <div className="field">
          <label>Type de document</label>
          <select
            value={typeDocument}
            onChange={(e) => setTypeDocument(e.target.value)}
          >
            <option value="procedure">Procédure</option>
            <option value="protocole">Protocole</option>
            <option value="enregistrement">Enregistrement</option>
            <option value="formulaire">Formulaire</option>
          </select>
        </div>

        <div className="field">
          <label>Justification</label>
          <textarea
            value={justification}
            onChange={(e) => setJustification(e.target.value)}
            rows={4}
            required
          />
        </div>

        <div className="field">
          <label>Service concerné</label>
          <select
            value={serviceId}
            onChange={(e) => setServiceId(Number(e.target.value))}
            required
          >
            <option value="">-- Choisir --</option>
            {services.map((s) => (
              <option key={s.id} value={s.id}>
                {s.nom}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label>Email du responsable de service</label>
          <input
            type="email"
            value={responsableEmail}
            onChange={(e) => setResponsableEmail(e.target.value)}
            required
          />
        </div>

        {error && <p className="error">{error}</p>}
        {success && (
          <p className="success">Demande soumise avec succès — statut : en attente d'examen.</p>
        )}

        <button className="btn-primary" type="submit">
          Soumettre la demande
        </button>
      </form>
    </>
  );
}
