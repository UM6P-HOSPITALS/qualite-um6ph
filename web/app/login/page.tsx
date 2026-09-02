"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const res = await fetch(`${API_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || "Échec de la connexion");
      }
      const data = await res.json();
      localStorage.setItem("token", data.access_token);
      router.push("/documents/nouvelle-demande");
    } catch (err: any) {
      setError(err.message);
    }
  }

  return (
    <>
      <div className="header-bar">
        <strong>QUALITE-UM6PH</strong>
      </div>
      <form className="card" onSubmit={handleSubmit}>
        <h2>Connexion</h2>
        <div className="field">
          <label>Email</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>
        <div className="field">
          <label>Mot de passe</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>
        {error && <p className="error">{error}</p>}
        <button className="btn-primary" type="submit">
          Se connecter
        </button>
      </form>
    </>
  );
}
