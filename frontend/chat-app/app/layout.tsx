import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Encrypted Chat",
  description: "End-to-end encrypted chat application",
    generator: 'v0.app'
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">
        {children}
      </body>
    </html>
  );
}
