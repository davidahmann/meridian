import Link from 'next/link';
import CodeBlock from '@/components/CodeBlock';

const QUICKSTART_CODE = `from fabra.core import FeatureStore, entity, feature
from fabra.context import context, ContextItem
from fabra.retrieval import retriever

store = FeatureStore()

@entity(store)
class User:
    user_id: str

@feature(entity=User, refresh="daily")
def user_tier(user_id: str) -> str:
    return "premium" if hash(user_id) % 2 == 0 else "free"

@retriever(index="docs", top_k=3)
async def find_docs(query: str):
    pass  # Automatic vector search

@context(store, max_tokens=4000)
async def build_prompt(user_id: str, query: str):
    tier = await store.get_feature("user_tier", user_id)
    docs = await find_docs(query)
    return [
        ContextItem(content=f"User is {tier}.", priority=0),
        ContextItem(content=str(docs), priority=1),
    ]`;

export default function Home() {
  return (
    <div className="not-prose">
      {/* Hero Section */}
      <div className="text-center py-12 lg:py-20">
        <h1 className="text-4xl lg:text-6xl font-bold text-white mb-6">
          Stop Debugging AI Decisions{' '}
          <span className="bg-gradient-to-r from-cyan-400 to-purple-500 bg-clip-text text-transparent">
            You Can&apos;t Reproduce
          </span>
        </h1>
        <p className="text-xl text-gray-400 max-w-2xl mx-auto mb-8">
          When your AI gives a bad answer, you need to know: What did it see? What got dropped?
          Fabra turns &quot;the AI was wrong&quot; into a fixable ticket.
        </p>
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <Link
            href="/docs/quickstart"
            className="px-6 py-3 bg-cyan-500 hover:bg-cyan-400 text-gray-900 font-semibold rounded-lg transition-colors"
          >
            Get Started
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
          <code className="text-cyan-400 text-sm">pip install fabra-ai</code>
        </div>
      </div>

      {/* Features Grid */}
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6 mb-16">
        <FeatureCard
          icon="🔄"
          title="Replay Any Decision"
          description="See exactly what your AI knew at any point in time. Reproduce incidents in seconds."
          href="/docs/context-accountability"
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
          href="/docs/freshness-sla"
        />
      </div>

      {/* Code Example */}
      <div className="mb-16">
        <h2 className="text-2xl font-bold text-white mb-6 text-center">30-Second Quickstart</h2>
        <CodeBlock code={QUICKSTART_CODE} language="python" filename="features.py" />
        <div className="text-center mt-4">
          <code className="text-gray-400 text-sm">
            $ fabra serve features.py
          </code>
        </div>
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
