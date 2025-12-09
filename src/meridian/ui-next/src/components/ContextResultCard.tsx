'use client';

import type { ContextResult } from '@/types/api';

interface ContextResultCardProps {
  result: ContextResult;
}

export default function ContextResultCard({ result }: ContextResultCardProps) {
  const tokenUsage = result.meta.token_usage ?? 'N/A';
  const cost = result.meta.cost_usd ?? 0;
  const latency = result.meta.latency_ms ?? 0;
  const freshness = result.meta.freshness_status ?? 'N/A';

  const getFreshnessColor = () => {
    if (freshness === 'guaranteed') return 'text-green-500';
    if (freshness === 'N/A') return 'text-gray-500';
    return 'text-amber-500';
  };

  return (
    <div className="bg-gradient-to-br from-gray-800 to-gray-900 border border-gray-700 rounded-xl p-6 shadow-xl">
      {/* Header */}
      <div className="flex justify-between items-center mb-5 pb-4 border-b border-gray-700">
        <div className="font-mono text-xs text-gray-500 bg-gray-900 px-2 py-1 rounded">
          ID: {result.id}
        </div>
        <div className="bg-green-500/20 text-green-500 px-3 py-1 rounded-full text-xs font-semibold">
          Assembled
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="bg-gray-900 border border-gray-700 rounded-lg p-4 text-center">
          <div className="text-xs text-gray-500 uppercase tracking-wide mb-2">
            Tokens
          </div>
          <div className="text-xl font-bold text-green-500">{tokenUsage}</div>
        </div>
        <div className="bg-gray-900 border border-gray-700 rounded-lg p-4 text-center">
          <div className="text-xs text-gray-500 uppercase tracking-wide mb-2">
            Cost
          </div>
          <div className="text-xl font-bold text-amber-500">
            ${typeof cost === 'number' ? cost.toFixed(6) : cost}
          </div>
        </div>
        <div className="bg-gray-900 border border-gray-700 rounded-lg p-4 text-center">
          <div className="text-xs text-gray-500 uppercase tracking-wide mb-2">
            Latency
          </div>
          <div className="text-xl font-bold text-blue-500">
            {typeof latency === 'number' ? `${latency.toFixed(1)}ms` : latency}
          </div>
        </div>
        <div className="bg-gray-900 border border-gray-700 rounded-lg p-4 text-center">
          <div className="text-xs text-gray-500 uppercase tracking-wide mb-2">
            Freshness
          </div>
          <div className={`text-xl font-bold ${getFreshnessColor()}`}>
            {freshness}
          </div>
        </div>
      </div>

      {/* Context Items */}
      <div>
        <div className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">
          Context Items
        </div>
        <div className="space-y-2 max-h-[300px] overflow-y-auto">
          {result.items && result.items.length > 0 ? (
            result.items.slice(0, 5).map((item, idx) => (
              <div
                key={idx}
                className="bg-gray-900 border border-gray-700 rounded-lg p-3"
              >
                <div className="text-gray-300 text-sm font-mono whitespace-pre-wrap">
                  {String(item.content).length > 100
                    ? `${String(item.content).slice(0, 100)}...`
                    : item.content}
                </div>
                <span className="bg-gray-700 text-gray-400 px-2 py-1 rounded text-xs mt-2 inline-block">
                  P{item.priority}
                </span>
              </div>
            ))
          ) : (
            <div className="text-gray-500 italic">No items</div>
          )}
        </div>
      </div>
    </div>
  );
}
