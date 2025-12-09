'use client';

import { examples, Example } from '@/lib/examples';

interface ExampleSelectorProps {
  selectedId: string;
  onSelect: (example: Example) => void;
}

const categoryLabels: Record<Example['category'], string> = {
  'feature-store': 'Feature Store',
  'context-store': 'Context Store',
  rag: 'RAG',
  accountability: 'Accountability',
};

const categoryColors: Record<Example['category'], string> = {
  'feature-store': 'bg-blue-500',
  'context-store': 'bg-purple-500',
  rag: 'bg-green-500',
  accountability: 'bg-amber-500',
};

export default function ExampleSelector({
  selectedId,
  onSelect,
}: ExampleSelectorProps) {
  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-gray-300 mb-2">
        Examples
      </label>
      <div className="grid grid-cols-1 gap-2">
        {examples.map((example) => (
          <button
            key={example.id}
            onClick={() => onSelect(example)}
            className={`text-left p-3 rounded-lg border transition-all ${
              selectedId === example.id
                ? 'border-meridian-500 bg-meridian-500/10'
                : 'border-gray-700 hover:border-gray-600 bg-gray-800/50'
            }`}
          >
            <div className="flex items-center gap-2 mb-1">
              <span
                className={`text-xs px-2 py-0.5 rounded-full text-white ${
                  categoryColors[example.category]
                }`}
              >
                {categoryLabels[example.category]}
              </span>
              <span className="text-sm font-medium text-white">
                {example.title}
              </span>
            </div>
            <p className="text-xs text-gray-400">{example.description}</p>
          </button>
        ))}
      </div>
    </div>
  );
}
