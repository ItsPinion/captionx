import type { Metadata } from "next";
import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "Image–Caption Extraction | NCERT PDF Automation",
  description:
    "Extract images and captions from Grade 9 NCERT PDFs automatically — PyMuPDF + PaddleOCR + spatial/textual matching.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
