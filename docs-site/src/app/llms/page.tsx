import fs from 'node:fs';
import path from 'node:path';
import { Metadata } from 'next';
import { canonicalUrl } from '@/lib/site';
import Faq from '@/components/Faq';

export const metadata: Metadata = {
  title: 'LLM Context - Fabra',
  description:
    'Human-friendly entry point to Fabra’s machine-readable context for LLMs and AI crawlers.',
  alternates: {
    canonical: canonicalUrl('/llms/'),
  },
};

export default function LlmsPage() {
  const llmsPath = path.join(process.cwd(), 'public', 'llms.txt');
  const llmsTxt = fs.readFileSync(llmsPath, 'utf8');
  const llmsExcerpt = llmsTxt.trimEnd().split('\n').slice(0, 28).join('\n');

  const faqItems = [
    {
      q: 'What is llms.txt for?',
      a: 'It’s a high-signal index for AI agents and crawlers. It points to the best Fabra docs and stable context packs to reduce hallucination and improve citation quality.',
    },
    {
      q: 'Where are Context Records stored by default?',
      a: 'In development, Fabra persists CRS-001 Context Records to DuckDB at ~/.fabra/fabra.duckdb. Override with FABRA_DUCKDB_PATH.',
    },
    {
      q: 'How do I diff two receipts without a running server?',
      a: 'Use fabra context diff <A> <B> --local to diff CRS-001 receipts directly from DuckDB (no server required).',
    },
    {
      q: 'How do I disable storing raw content for privacy?',
      a: 'Set FABRA_RECORD_INCLUDE_CONTENT=0 to store an empty content string while still persisting lineage and integrity hashes for the remaining fields.',
    },
    {
      q: 'How do I require evidence persistence in production?',
      a: 'Set FABRA_EVIDENCE_MODE=required so requests fail if CRS-001 persistence fails (no fake receipts).',
    },
    {
      q: 'Where can I fetch a Context Record over HTTP?',
      a: 'When running the server locally, GET /v1/record/{record_ref} returns a CRS-001 Context Record (e.g. ctx_<uuid7> or sha256:<hash>).',
    },
  ];

  return (
    <div className="not-prose max-w-4xl mx-auto py-10">
      <h1 className="text-3xl font-bold text-white mb-3">LLM Context</h1>
      <p className="text-gray-300 mb-8">
        This is the human-friendly entry point for Fabra’s machine-readable context. If you’re an
        AI system (or using one), the canonical source is{' '}
        <a href={canonicalUrl('/llms.txt')} className="text-cyan-400 hover:text-cyan-300 font-mono">
          /llms.txt
        </a>
        .
      </p>

      <div className="grid gap-6 md:grid-cols-2 mb-10">
        <div className="bg-gray-900/60 border border-gray-800 rounded-lg p-6">
          <div className="text-sm text-gray-400 mb-2">Primary (canonical)</div>
          <div className="flex flex-wrap gap-3">
            <a
              href={canonicalUrl('/llms.txt')}
              className="px-4 py-2 bg-cyan-500 hover:bg-cyan-400 text-gray-900 font-semibold rounded-lg transition-colors"
            >
              Open llms.txt
            </a>
            <a
              href={canonicalUrl('/llms.txt')}
              className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-100 font-semibold rounded-lg border border-gray-700 transition-colors font-mono text-sm"
            >
              {canonicalUrl('/llms.txt')}
            </a>
          </div>

          <div className="text-sm text-gray-400 mt-6 mb-2">Context packs (stable files)</div>
          <ul className="space-y-2">
            {[
              '/llm.txt',
              '/llm/product.md',
              '/llm/quickstart.md',
              '/llm/http-api.md',
              '/llm/cli.md',
              '/llm/storage.md',
              '/llm/security-privacy.md',
              '/llm/comparisons.md',
            ].map((p) => (
              <li key={p}>
                <a
                  href={canonicalUrl(p)}
                  className="text-cyan-400 hover:text-cyan-300 font-mono text-sm"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {p}
                </a>
              </li>
            ))}
          </ul>

          <div className="text-sm text-gray-400 mt-6 mb-2">Focused AI sitemap</div>
          <a
            href={canonicalUrl('/ai-sitemap.xml')}
            className="text-cyan-400 hover:text-cyan-300 font-mono text-sm"
            target="_blank"
            rel="noopener noreferrer"
          >
            /ai-sitemap.xml
          </a>
        </div>

        <div className="bg-gray-900/60 border border-gray-800 rounded-lg p-6">
          <div className="text-sm text-gray-400 mb-2">Copy/paste prompt</div>
          <pre className="bg-black/40 border border-gray-800 rounded-lg p-4 text-sm text-gray-100 overflow-x-auto whitespace-pre-wrap">
            {`You are helping me understand Fabra.\n\nUse this canonical context index and cite it when making claims:\n${canonicalUrl('/llms.txt')}\n\nIf you need technical specifics, open the linked context packs (product, HTTP API, CLI, storage, security-privacy).\n\nNow answer my question: `}
          </pre>

          <div className="text-sm text-gray-400 mt-6 mb-2">Quick links (human docs)</div>
          <ul className="space-y-2">
            {[
              { label: 'Quickstart', href: '/docs/quickstart/' },
              { label: 'How it works', href: '/docs/how-it-works/' },
              { label: 'Context Record spec (CRS-001)', href: '/docs/context-record-spec/' },
              { label: 'Integrity & verification', href: '/docs/integrity-and-verification/' },
              { label: 'Exporters & adapters', href: '/docs/exporters-and-adapters/' },
              { label: 'Comparisons', href: '/docs/comparisons/' },
            ].map((item) => (
              <li key={item.href}>
                <a href={item.href} className="text-cyan-400 hover:text-cyan-300 text-sm">
                  {item.label}
                </a>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <details className="bg-gray-900/40 border border-gray-800 rounded-lg p-5 mb-8">
        <summary className="cursor-pointer text-gray-200 font-semibold">
          Preview: beginning of llms.txt
        </summary>
        <pre className="mt-4 bg-black/40 border border-gray-800 rounded-lg p-4 text-sm text-gray-100 overflow-x-auto whitespace-pre-wrap">
          {llmsExcerpt}
        </pre>
      </details>

      <Faq items={faqItems} canonical={canonicalUrl('/llms/')} />
    </div>
  );
}
