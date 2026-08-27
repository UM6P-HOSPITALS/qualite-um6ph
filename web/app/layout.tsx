export const metadata = {
  title: "QUALITE-UM6PH — Plateforme Qualité UM6P Hospitals",
  description: "Gestion documentaire, événements indésirables et audits",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="fr">
      <body>{children}</body>
    </html>
  );
}
