import type { Metadata } from "next";

import "./globals.css";
import { SiteHeader } from "@/components/site-header";
import { ThemeProvider } from "@/components/theme-provider";

export const metadata: Metadata = {
  title: { default: "DemoWeb 게시판", template: "%s | DemoWeb 게시판" },
  description: "Next.js와 shadcn/ui로 만든 데모 게시판",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko" suppressHydrationWarning>
      <body className="min-h-screen antialiased">
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
          <SiteHeader />
          <main className="mx-auto w-full max-w-5xl px-4 py-6 sm:py-10">{children}</main>
        </ThemeProvider>
      </body>
    </html>
  );
}
