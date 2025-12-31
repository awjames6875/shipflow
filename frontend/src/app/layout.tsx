import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'Viral News to AI Avatar | ShipFlow',
  description: 'Automatically create AI avatar videos from trending news and post to all social platforms',
  keywords: ['AI avatar', 'viral news', 'social media automation', 'HeyGen', 'content creation'],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>{children}</body>
    </html>
  );
}
