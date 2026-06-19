import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "RecruitNinja — AI Hiring Platform",
  description: "Generate, manage, and analyse Job Descriptions with AI",
  icons: {
    icon: "/wissen_logo.png",
    shortcut: "/wissen_logo.png",
    apple: "/wissen_logo.png",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
