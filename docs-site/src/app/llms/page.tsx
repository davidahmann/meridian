import Link from 'next/link';
import { Metadata } from 'next';
import { canonicalUrl } from '@/lib/site';

export const metadata: Metadata = {
  title: 'LLM Context - Fabra',
  description: 'Machine-readable context and high-signal references for LLMs and AI crawlers.',
  alternates: {
    canonical: canonicalUrl('/llms/'),
  },
};

export default function LlmsPage() {
  return (
    <div className="not-prose max-w-3xl mx-auto py-10">
      <h1 className="text-3xl font-bold text-white mb-4">LLM Context</h1>
      <p className="text-gray-300 mb-8">
        This page is a human-friendly entry point. For AI agent discovery, use the plain-text
        context file:
      </p>

      <div className="bg-gray-900/60 border border-gray-800 rounded-lg p-5 mb-8">
        <div className="text-sm text-gray-400 mb-2">Primary</div>
        <Link
          href="/llms.txt"
          className="text-cyan-400 hover:text-cyan-300 font-mono text-sm"
        >
          /llms.txt
        </Link>

        <div className="text-sm text-gray-400 mt-5 mb-2">Additional context packs</div>
        <ul className="space-y-2">
          <li>
            <Link href="/llm.txt" className="text-cyan-400 hover:text-cyan-300 font-mono text-sm">
              /llm.txt
            </Link>
          </li>
          <li>
            <Link href="/llm/product.md" className="text-cyan-400 hover:text-cyan-300 font-mono text-sm">
              /llm/product.md
            </Link>
          </li>
          <li>
            <Link href="/llm/http-api.md" className="text-cyan-400 hover:text-cyan-300 font-mono text-sm">
              /llm/http-api.md
            </Link>
          </li>
          <li>
            <Link href="/llm/cli.md" className="text-cyan-400 hover:text-cyan-300 font-mono text-sm">
              /llm/cli.md
            </Link>
          </li>
          <li>
            <Link href="/llm/comparisons.md" className="text-cyan-400 hover:text-cyan-300 font-mono text-sm">
              /llm/comparisons.md
            </Link>
          </li>
        </ul>

        <div className="text-sm text-gray-400 mt-5 mb-2">Focused AI sitemap</div>
        <Link
          href="/ai-sitemap.xml"
          className="text-cyan-400 hover:text-cyan-300 font-mono text-sm"
        >
          /ai-sitemap.xml
        </Link>
      </div>

      <p className="text-gray-400 text-sm">
        If you arrived here via a link to <span className="font-mono">/llms</span>, you’re in the
        right place — the canonical, machine-readable source is{' '}
        <Link href="/llms.txt" className="text-cyan-400 hover:text-cyan-300">
          /llms.txt
        </Link>
        .
      </p>
    </div>
  );
}
