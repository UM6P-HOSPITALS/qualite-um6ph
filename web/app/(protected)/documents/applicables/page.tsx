"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import AppHeader from "@/components/AppHeader";

interface ApplicableDoc {
  id: number;
  intitule: string;
  type_document: string;
  service_nom: string;
  date_diffusion: string | null;
  deja_lu: boolean;
}

export default function ApplicablesPage() {
  const [documents, setDocuments] = useState<ApplicableDoc[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch("/documents/applicable").then(setDocuments).catch((err) => setError(err.message));
  }, []);

  return (
    <>
      <AppHeader title="Documents applicables" />
      <div style={{ maxWidth: 800, margin: "2rem auto" }}>
        {error && <p className="error">{error}</p>}
        {documents.length === 0 && <p>Aucun document diffusé pour votre service.</p>}

        {documents.map((d) => (
          <div key={d.id} className="card" style={{ margin: "1rem auto" }}>
            <h3>{d.intitule}</h3>
            <p style={{ color: "#6b7280" }}>
              {d.type_document} — {d.service_nom}
              {d.date_diffusion && ` — diffusé le ${new Date(d.date_diffusion).toLocaleDateString()}`}
            </p>
            <p>
              {d.deja_lu ? (
                <span className="success">Déjà lu</span>
              ) : (
                <span style={{ color: "#c0392b" }}>Non lu</span>
              )}
            </p>
            <Link href={`/documents/${d.id}/lire`}>
              <button className="btn-primary">Lire le document</button>
            </Link>
          </div>
        ))}
      </div>
    </>
  );
}