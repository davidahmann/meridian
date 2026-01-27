import Link from 'next/link';
import CodeBlock from '@/components/CodeBlock';
import { Metadata } from 'next';
import { canonicalUrl } from '@/lib/site';

export const metadata: Metadata = {
  title: 'Fabra - Record → Replay → Diff',
  description:
    "Fabra makes AI context durable. Every request becomes a replayable Context Record, so you can answer: what did it see, and what changed? Record → replay → diff. Turn 'the AI was wrong' into a fixable ticket.",
  alternates: {
    canonical: canonicalUrl('/'),
  },
};

const QUICKSTART_CODE = `pip install fabra-ai
fabra demo

# You'll see a context_id printed (your receipt)
fabra context show <context_id>
fabra context verify <context_id>

# Generate a second record, then diff drift
fabra context diff <context_id_A> <context_id_B>`;

export default function Home() {
  return (
    <div className="not-prose">
      {/* Hero Section */}
      <div className="text-center py-12 lg:py-20">
        <h1 className="text-4xl lg:text-6xl font-bold text-white mb-6">
          Turn AI Incidents Into{' '}
          <span className="bg-gradient-to-r from-cyan-400 to-purple-500 bg-clip-text text-transparent">
            Reproducible Tickets
          </span>
        </h1>
        <p className="text-xl text-gray-400 max-w-2xl mx-auto mb-8">
          When your AI misbehaves, you need evidence: what did it see, and what changed?
          No more vibes and screenshots. Fabra makes inference context a durable artifact you can replay, diff, and verify.
        </p>
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <Link
            href="/docs/quickstart"
            className="px-6 py-3 bg-cyan-500 hover:bg-cyan-400 text-gray-900 font-semibold rounded-lg transition-colors"
          >
            Get Started
          </Link>
          <Link
            href="/llms"
            className="px-6 py-3 bg-gray-800 hover:bg-gray-700 text-gray-100 font-semibold rounded-lg border border-gray-700 transition-colors"
          >
            LLM Context
          </Link>
          <a
            href="https://fabraoss.vercel.app"
            target="_blank"
            rel="noopener noreferrer"
            className="px-6 py-3 bg-gray-800 hover:bg-gray-700 text-gray-100 font-semibold rounded-lg border border-gray-700 transition-colors"
          >
            Try in Browser
          </a>
        </div>
      </div>

      {/* Quick Install */}
      <div className="max-w-xl mx-auto mb-16">
        <div className="bg-gray-800/50 rounded-lg border border-gray-700 p-4">
          <code className="text-cyan-400 text-sm">pip install fabra-ai &amp;&amp; fabra demo</code>
        </div>
      </div>

      {/* Features Grid */}
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6 mb-16">
        <FeatureCard
          icon="🔄"
          title="Replay Any Decision"
          description="See exactly what your AI knew at any point in time. Reproduce incidents in seconds."
          href="/docs/incident-playbook"
        />
        <FeatureCard
          icon="📋"
          title="Shareable Tickets"
          description="Turn 'it was wrong' into a Context Record you can share, diff, and fix."
          href="/docs/context-store"
        />
        <FeatureCard
          icon="🚀"
          title="Ship Confidently"
          description="Debug regressions before they hit production. Know what changed between decisions."
          href="/docs/context-assembly"
        />
        <FeatureCard
          icon="🔍"
          title="Explain Dropped Items"
          description="Know exactly what got cut due to token limits — and why."
          href="/docs/token-budget-management"
        />
        <FeatureCard
          icon="⚡"
          title="30-Second Setup"
          description="pip install, no Kubernetes. DuckDB locally, Postgres in production."
          href="/docs/local-to-production"
        />
        <FeatureCard
          icon="🛡️"
          title="Prove What Happened"
          description="Cryptographic integrity. When compliance asks, you have the answer."
          href="/docs/integrity-and-verification"
        />
      </div>

      {/* Code Example */}
      <div className="mb-16">
        <h2 className="text-2xl font-bold text-white mb-6 text-center">2 Minutes to Your First Context Record</h2>
        <CodeBlock code={QUICKSTART_CODE} language="bash" filename="quickstart.sh" />
      </div>

      {/* Comparison Table */}
      <div className="mb-16">
        <h2 className="text-2xl font-bold text-white mb-6 text-center">Why Fabra?</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-700">
                <th className="text-left py-3 px-4 text-gray-400"></th>
                <th className="text-left py-3 px-4 text-gray-400">Without Fabra</th>
                <th className="text-left py-3 px-4 text-cyan-400">With Fabra</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              <tr>
                <td className="py-3 px-4 text-gray-300 font-medium">Can you prove what happened?</td>
                <td className="py-3 px-4 text-gray-500">Logs, maybe</td>
                <td className="py-3 px-4 text-gray-300">Full Context Record</td>
              </tr>
              <tr>
                <td className="py-3 px-4 text-gray-300 font-medium">Can you replay a decision?</td>
                <td className="py-3 px-4 text-gray-500">No</td>
                <td className="py-3 px-4 text-gray-300">Yes, built-in</td>
              </tr>
              <tr>
                <td className="py-3 px-4 text-gray-300 font-medium">Why did it miss something?</td>
                <td className="py-3 px-4 text-gray-500">Unknown</td>
                <td className="py-3 px-4 text-gray-300">Dropped items logged</td>
              </tr>
              <tr>
                <td className="py-3 px-4 text-gray-300 font-medium">Incident resolution</td>
                <td className="py-3 px-4 text-gray-500">Hours of guesswork</td>
                <td className="py-3 px-4 text-gray-300">Minutes with replay</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* CTA */}
      <div className="text-center py-12 border-t border-gray-800">
        <h2 className="text-2xl font-bold text-white mb-4">Ready to stop guessing?</h2>
        <p className="text-gray-400 mb-6">From pip install to replayable AI decisions in 30 seconds.</p>
        <Link
          href="/docs/quickstart"
          className="inline-block px-6 py-3 bg-cyan-500 hover:bg-cyan-400 text-gray-900 font-semibold rounded-lg transition-colors"
        >
          Read the Quickstart Guide
        </Link>
      </div>
    </div>
  );
}

function FeatureCard({
  icon,
  title,
  description,
  href,
}: {
  icon: string;
  title: string;
  description: string;
  href: string;
}) {
  return (
    <Link
      href={href}
      className="block p-6 bg-gray-800/30 hover:bg-gray-800/50 rounded-lg border border-gray-700 hover:border-gray-600 transition-colors"
    >
      <span className="text-2xl mb-3 block">{icon}</span>
      <h3 className="text-lg font-semibold text-white mb-2">{title}</h3>
      <p className="text-sm text-gray-400">{description}</p>
    </Link>
  );
}
