import type { Metadata } from 'next';
import './globals.css';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';

export const metadata: Metadata = {
  title: 'Fabra - Record What Your AI Saw',
  description: 'Fabra records what your AI saw — so you can replay and debug it. Creates a replayable Context Record for every AI call: what data was used, where it came from, what got dropped, and why.',
  keywords: 'context record, ai debugging, rag audit trail, llm replay, feature store, context lineage, mlops, pgvector, vector search',
  openGraph: {
    title: 'Fabra - Record What Your AI Saw',
    description: 'Fabra records what your AI saw — so you can replay and debug it. Creates a replayable Context Record for every AI call.',
    url: 'https://davidahmann.github.io/fabra',
    siteName: 'Fabra',
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Fabra - Record What Your AI Saw',
    description: 'Fabra records what your AI saw — so you can replay and debug it. Creates a replayable Context Record for every AI call.',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased">
        <Header />
        <div className="flex max-w-7xl mx-auto px-4 lg:px-8">
          <Sidebar />
          <main className="flex-1 min-w-0 py-8 lg:pl-8">
            <article className="prose prose-invert max-w-none">
              {children}
            </article>
          </main>
        </div>
      </body>
    </html>
  );
}
