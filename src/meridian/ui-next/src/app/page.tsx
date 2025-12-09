'use client';

import { useState, useEffect } from 'react';
import useSWR from 'swr';
import type { StoreInfo } from '@/types/api';
import { getStoreInfo, getMermaidGraph } from '@/lib/api';
import Sidebar from '@/components/Sidebar';
import StoreTab from '@/components/StoreTab';
import ContextTab from '@/components/ContextTab';

type Tab = 'store' | 'context';

export default function Home() {
  const [activeTab, setActiveTab] = useState<Tab>('store');

  const { data: storeInfo, error: storeError, isLoading } = useSWR<StoreInfo>(
    '/api/store',
    () => getStoreInfo(),
    { revalidateOnFocus: false }
  );

  const { data: graphData } = useSWR(
    '/api/graph',
    () => getMermaidGraph(),
    { revalidateOnFocus: false }
  );

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-gray-900 to-gray-950">
        <div className="text-center">
          <svg
            className="animate-spin h-12 w-12 text-green-500 mx-auto mb-4"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
              fill="none"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
            />
          </svg>
          <div className="text-gray-400">Loading Meridian UI...</div>
        </div>
      </div>
    );
  }

  if (storeError) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-gray-900 to-gray-950">
        <div className="bg-red-500/10 border border-red-500 rounded-lg p-6 max-w-md text-center">
          <div className="text-red-500 text-lg font-semibold mb-2">
            Failed to Load
          </div>
          <div className="text-gray-400">
            Could not connect to Meridian API. Make sure the server is running.
          </div>
        </div>
      </div>
    );
  }

  if (!storeInfo) {
    return null;
  }

  return (
    <div className="min-h-screen flex bg-gradient-to-b from-gray-900 to-gray-950">
      {/* Sidebar */}
      <Sidebar
        fileName={storeInfo.file_name}
        retrievers={storeInfo.retrievers}
      />

      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <header className="bg-gray-900/80 backdrop-blur-sm border-b border-gray-800 sticky top-0 z-10">
          <div className="px-6 py-4">
            <div className="flex items-center gap-3">
              <div className="text-2xl">🧭</div>
              <h1 className="text-xl font-bold text-gray-100">Meridian</h1>
            </div>
          </div>
        </header>

        {/* Tabs */}
        <div className="px-6 py-4">
          <div className="bg-gray-800 rounded-lg p-1 inline-flex gap-1">
            <button
              onClick={() => setActiveTab('store')}
              className={`px-4 py-2 rounded-md font-medium text-sm transition ${
                activeTab === 'store'
                  ? 'bg-gray-700 text-gray-100'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              Store & Features
            </button>
            <button
              onClick={() => setActiveTab('context')}
              className={`px-4 py-2 rounded-md font-medium text-sm transition ${
                activeTab === 'context'
                  ? 'bg-gray-700 text-gray-100'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              Context Assembly
            </button>
          </div>
        </div>

        {/* Tab Content */}
        <main className="flex-1 px-6 pb-6 overflow-auto">
          {activeTab === 'store' && (
            <StoreTab
              entities={storeInfo.entities}
              features={storeInfo.features}
              mermaidCode={graphData?.code || ''}
              onlineStoreType={storeInfo.online_store_type}
            />
          )}
          {activeTab === 'context' && (
            <ContextTab contexts={storeInfo.contexts} />
          )}
        </main>
      </div>
    </div>
  );
}
