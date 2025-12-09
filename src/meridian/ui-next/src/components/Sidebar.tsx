'use client';

import type { Retriever } from '@/types/api';

interface SidebarProps {
  fileName: string;
  retrievers: Retriever[];
}

export default function Sidebar({ fileName, retrievers }: SidebarProps) {
  return (
    <aside className="w-64 bg-gray-800 border-r border-gray-700 flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-gray-700">
        <h3 className="text-gray-100 font-semibold flex items-center gap-2">
          <span>Configuration</span>
        </h3>
      </div>

      {/* Loaded File */}
      <div className="p-4">
        <div className="bg-gray-900 border border-gray-700 rounded-lg p-3">
          <div className="text-xs text-gray-500 uppercase tracking-wide mb-1">
            Loaded File
          </div>
          <div className="text-green-500 font-mono text-sm truncate">
            {fileName}
          </div>
        </div>
      </div>

      {/* Retrievers */}
      {retrievers.length > 0 && (
        <div className="p-4 pt-0">
          <div className="text-gray-100 font-semibold mb-3 flex items-center gap-2">
            <span>Retrievers</span>
          </div>
          <div className="space-y-2">
            {retrievers.map((retriever) => (
              <div
                key={retriever.name}
                className="bg-gray-900 border border-gray-700 rounded-lg p-3"
              >
                <div className="text-blue-500 font-semibold text-sm">
                  {retriever.name}
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  Backend:{' '}
                  <span className="text-gray-400">{retriever.backend}</span>
                  {' | '}
                  TTL:{' '}
                  <span className="text-gray-400">{retriever.cache_ttl}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Spacer */}
      <div className="flex-1" />

      {/* Footer */}
      <div className="p-4 border-t border-gray-700">
        <div className="text-xs text-gray-500 text-center">
          Meridian UI v0.1
        </div>
      </div>
    </aside>
  );
}
