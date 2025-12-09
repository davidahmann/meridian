'use client';

import type { Feature } from '@/types/api';

interface FeatureCardProps {
  feature: Feature;
  value: unknown;
}

export default function FeatureCard({ feature, value }: FeatureCardProps) {
  const valueStr = value !== null && value !== undefined ? String(value) : '—';
  const valueColor = value !== null && value !== undefined ? 'text-green-500' : 'text-gray-500';

  // Determine font size based on value complexity
  const isComplex = valueStr.length > 30 || typeof value === 'object';
  const fontSize = isComplex ? 'text-sm' : 'text-xl';

  // Truncate very long values
  const displayValue = valueStr.length > 100 ? `${valueStr.slice(0, 100)}...` : valueStr;

  return (
    <div className="bg-gradient-to-br from-gray-800 to-gray-900 border border-gray-700 rounded-lg p-5 shadow-lg">
      {/* Feature name */}
      <div className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-2">
        {feature.name}
      </div>

      {/* Value */}
      <div className={`${fontSize} font-semibold ${valueColor} mb-3 break-words leading-relaxed`}>
        {displayValue}
      </div>

      {/* Badges */}
      <div className="flex flex-wrap gap-2">
        {feature.materialize && (
          <span className="bg-red-500/20 text-red-500 px-2 py-1 rounded text-xs">
            Materialized
          </span>
        )}
        {feature.refresh && (
          <span className="bg-blue-500/20 text-blue-500 px-2 py-1 rounded text-xs">
            {feature.refresh}
          </span>
        )}
        {feature.ttl && (
          <span className="bg-amber-500/20 text-amber-500 px-2 py-1 rounded text-xs">
            TTL: {feature.ttl}
          </span>
        )}
      </div>
    </div>
  );
}
