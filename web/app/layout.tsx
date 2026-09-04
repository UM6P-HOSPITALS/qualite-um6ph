import "./globals.css";

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
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=Dancing+Script:wght@700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}