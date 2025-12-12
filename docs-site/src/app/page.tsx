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
          Record What Your AI Saw{' '}
          <span className="bg-gradient-to-r from-cyan-400 to-purple-500 bg-clip-text text-transparent">
            &mdash; Replay &amp; Debug It
          </span>
        </h1>
        <p className="text-xl text-gray-400 max-w-2xl mx-auto mb-8">
          Fabra creates a replayable Context Record for every AI call: what data was used,
          where it came from, what got dropped, and why.
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
          icon="🎯"
          title="Context Store"
          description="Built-in pgvector for semantic search. Automatic chunking, embedding, and retrieval."
          href="/docs/context-store"
        />
        <FeatureCard
          icon="🔄"
          title="Feature Store"
          description="Python decorators instead of YAML. No Kubernetes required."
          href="/docs/feature-store-without-kubernetes"
        />
        <FeatureCard
          icon="📊"
          title="Token Budgets"
          description="Automatic context assembly that fits your LLM's window. Priority-based truncation."
          href="/docs/context-assembly"
        />
        <FeatureCard
          icon="🔍"
          title="Full Lineage"
          description="Track exactly what data informed each AI decision. Context replay for debugging."
          href="/docs/context-accountability"
        />
        <FeatureCard
          icon="⚡"
          title="Local to Production"
          description="DuckDB locally, Postgres + Redis in production. Same code, zero changes."
          href="/docs/local-to-production"
        />
        <FeatureCard
          icon="🛡️"
          title="Freshness SLAs"
          description="Guarantee data freshness with configurable thresholds and degraded mode."
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
                <th className="text-left py-3 px-4 text-gray-400">Traditional Stack</th>
                <th className="text-left py-3 px-4 text-cyan-400">Fabra</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              <tr>
                <td className="py-3 px-4 text-gray-300 font-medium">Config</td>
                <td className="py-3 px-4 text-gray-500">500 lines of YAML</td>
                <td className="py-3 px-4 text-gray-300">Python decorators</td>
              </tr>
              <tr>
                <td className="py-3 px-4 text-gray-300 font-medium">Infrastructure</td>
                <td className="py-3 px-4 text-gray-500">Kubernetes + Spark + Pinecone</td>
                <td className="py-3 px-4 text-gray-300">Your laptop (DuckDB)</td>
              </tr>
              <tr>
                <td className="py-3 px-4 text-gray-300 font-medium">RAG Pipeline</td>
                <td className="py-3 px-4 text-gray-500">LangChain spaghetti</td>
                <td className="py-3 px-4 text-gray-300">@retriever + @context</td>
              </tr>
              <tr>
                <td className="py-3 px-4 text-gray-300 font-medium">Time to Production</td>
                <td className="py-3 px-4 text-gray-500">Weeks</td>
                <td className="py-3 px-4 text-gray-300">30 seconds</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* CTA */}
      <div className="text-center py-12 border-t border-gray-800">
        <h2 className="text-2xl font-bold text-white mb-4">Ready to get started?</h2>
        <p className="text-gray-400 mb-6">From notebook to production in 30 seconds.</p>
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
