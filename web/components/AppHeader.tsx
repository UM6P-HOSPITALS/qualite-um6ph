"use client";

import { useRouter } from "next/navigation";
import { LogOut, ShieldCheck } from "lucide-react";
import { logout } from "@/lib/auth";

export default function AppHeader({ title }: { title?: string }) {
  const router = useRouter();

  return (
    <div className="app-header">
      <div className="app-header-left">
        <div className="app-header-logo-wrap">
          <img
            className="app-header-logo"
            src="/images/logo_um6p_hospital_blanc.png"
            alt="UM6P Hospitals"
          />
        </div>
        <div className="app-header-titles">
          <strong>QUALITE-UM6PH</strong>
          {title && <span className="app-header-subtitle">{title}</span>}
        </div>
      </div>

      <div className="app-header-right">
        <div className="app-header-badge">
          <ShieldCheck size={13} />
          Session active
        </div>

        <button className="app-header-logout" onClick={() => logout(router)}>
          <span className="app-header-logout-shine" />
          <LogOut size={16} />
          Déconnexion
        </button>
      </div>
    </div>
  );
}