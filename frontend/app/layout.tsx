import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NinjaForge — AI Hiring Platform",
  description: "Generate, manage, and analyse Job Descriptions with AI",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}