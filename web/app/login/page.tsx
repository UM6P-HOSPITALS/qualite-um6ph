"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Mail,
  Lock,
  Eye,
  EyeOff,
  ArrowRight,
  ShieldCheck,
  Sparkles,
  FileText,
  AlertTriangle,
  ClipboardCheck,
} from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
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
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-screen">
      <div className="login-panel-brand">
        <div className="login-orb login-orb-1" />
        <div className="login-orb login-orb-2" />
        <div className="login-orb login-orb-3" />
        <div className="login-blob" />
        <div className="login-grid-overlay" />

        <div className="login-float-icons" aria-hidden="true">
          <span className="login-float-icon icon-1">
            <FileText size={22} />
          </span>
          <span className="login-float-icon icon-2">
            <AlertTriangle size={20} />
          </span>
          <span className="login-float-icon icon-3">
            <ClipboardCheck size={24} />
          </span>
        </div>

        <div className="login-badge-pill">
          <Sparkles size={13} />
          Management Qualité Nouvelle Génération
        </div>

        <div className="login-logo-wrap">
          <div className="login-logo-ring" />
          <img
            className="login-logo"
            src="/images/logo_um6p_hospital_blanc.png"
            alt="UM6P Hospitals"
          />
        </div>

        <div className="login-brand-body">
          <h1>
            QUALITE<span className="highlight">-UM6PH</span>
          </h1>
          <p>
            Plateforme de management de la qualité — gestion documentaire,
            événements indésirables et audits, centralisés et tracés.
          </p>

          <div className="login-stats">
            <div>
              <strong>3</strong>
              <span>MODULES</span>
            </div>
            <div>
              <strong>9</strong>
              <span>RÔLES</span>
            </div>
            <div>
              <strong>100%</strong>
              <span>TRAÇABLE</span>
            </div>
          </div>
        </div>

        <div className="login-copyright">
          © 2026 UM6P Hospitals — Tous droits réservés
        </div>
      </div>

      <div className="login-panel-form">
        <div className="login-form-glow" />

        <div className="login-card">
          <div className="login-card-badge">
            <ShieldCheck size={13} />
            Connexion sécurisée
          </div>

          <form className="login-form-inner" onSubmit={handleSubmit}>
            <h2>Bon retour</h2>
            <p className="subtitle">Connectez-vous pour accéder à la plateforme.</p>

            <div className="field">
              <label>Email</label>
              <div className="input-with-icon">
                <Mail size={18} />
                <input
                  type="email"
                  placeholder="votre@um6p.ma"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </div>
            </div>

            <div className="field">
              <label>Mot de passe</label>
              <div className="input-with-icon">
                <Lock size={18} />
                <input
                  type={showPassword ? "text" : "password"}
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
                <button
                  type="button"
                  className="toggle-eye"
                  onClick={() => setShowPassword(!showPassword)}
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>

            <div className="login-row">
              <label style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                <input type="checkbox" /> Se souvenir de moi
              </label>
              <a href="#">Mot de passe oublié ?</a>
            </div>

            {error && <p className="error">{error}</p>}

            <button className="btn-primary-full" type="submit" disabled={loading}>
              <span className="btn-shine" />
              {loading ? "Connexion..." : "Se connecter"}
              <ArrowRight size={18} />
            </button>

            <p className="login-footer-note">
              <ShieldCheck size={13} />
              Accès réservé au personnel autorisé. Toutes les connexions sont
              journalisées.
            </p>
          </form>
        </div>
      </div>
    </div>
  );
}