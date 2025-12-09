'use client';

import { useState } from 'react';
import type { ContextDefinition, ContextResult } from '@/types/api';
import { assembleContext } from '@/lib/api';
import ContextResultCard from './ContextResultCard';
import JsonViewer from './JsonViewer';

interface ContextTabProps {
  contexts: ContextDefinition[];
}

// Helper to build initial params from context parameters
function buildInitialParams(ctx: ContextDefinition | undefined): Record<string, string> {
  if (!ctx) return {};
  const initial: Record<string, string> = {};
  for (const param of ctx.parameters) {
    initial[param.name] = param.default || '';
  }
  return initial;
}

export default function ContextTab({ contexts }: ContextTabProps) {
  const [selectedContext, setSelectedContext] = useState<string>(
    contexts[0]?.name || ''
  );
  const selectedContextObj = contexts.find((c) => c.name === selectedContext);
  const [params, setParams] = useState<Record<string, string>>(() =>
    buildInitialParams(selectedContextObj)
  );
  const [result, setResult] = useState<ContextResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showRawJson, setShowRawJson] = useState(false);

  const handleParamChange = (paramName: string, value: string) => {
    setParams((prev) => ({ ...prev, [paramName]: value }));
  };

  const handleAssemble = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const contextResult = await assembleContext(selectedContext, params);
      setResult(contextResult);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to assemble context');
    } finally {
      setIsLoading(false);
    }
  };

  if (contexts.length === 0) {
    return (
      <div className="bg-blue-500/10 border border-blue-500 rounded-lg p-4 text-blue-500">
        No @context functions found in this file.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h3 className="text-xl font-semibold text-gray-100">Context Assembly</h3>

      {/* Context Selector */}
      <div>
        <label className="block text-sm font-medium text-gray-400 mb-2">
          Select Context Definition
        </label>
        <select
          value={selectedContext}
          onChange={(e) => {
            const newCtx = contexts.find((c) => c.name === e.target.value);
            setSelectedContext(e.target.value);
            setParams(buildInitialParams(newCtx));
            setResult(null);
            setError(null);
          }}
          className="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-2 text-gray-100 focus:border-green-500 focus:ring-1 focus:ring-green-500 outline-none"
        >
          {contexts.map((ctx) => (
            <option key={ctx.name} value={ctx.name}>
              {ctx.name}
            </option>
          ))}
        </select>
      </div>

      {/* Context Info */}
      {selectedContextObj && (
        <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
          <span className="text-green-500 font-mono font-semibold">
            {selectedContextObj.name}
          </span>
          <span className="text-gray-500 ml-2 text-sm">
            {selectedContextObj.description || 'No description'}
          </span>
        </div>
      )}

      {/* Parameter Form */}
      {selectedContextObj && selectedContextObj.parameters.length > 0 && (
        <div className="bg-gray-800 border border-gray-700 rounded-lg p-6">
          <div className="text-sm font-medium text-gray-400 mb-4">Inputs</div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {selectedContextObj.parameters.map((param) => (
              <div key={param.name}>
                <label className="block text-sm text-gray-400 mb-1">
                  {param.name}
                  <span className="text-gray-600 ml-1">({param.type})</span>
                </label>
                <input
                  type="text"
                  value={params[param.name] ?? ''}
                  onChange={(e) => handleParamChange(param.name, e.target.value)}
                  className="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-2 text-gray-100 focus:border-green-500 focus:ring-1 focus:ring-green-500 outline-none"
                  placeholder={`Enter ${param.name}...`}
                />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Assemble Button */}
      <button
        onClick={handleAssemble}
        disabled={isLoading}
        className={`px-6 py-3 rounded-lg font-semibold flex items-center gap-2 transition ${
          isLoading
            ? 'bg-gray-700 text-gray-400 cursor-not-allowed'
            : 'bg-green-600 hover:bg-green-500 text-white'
        }`}
      >
        {isLoading ? (
          <>
            <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
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
            Assembling...
          </>
        ) : (
          <>
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            Assemble Context
          </>
        )}
      </button>

      {/* Error Message */}
      {error && (
        <div className="bg-red-500/10 border border-red-500 rounded-lg p-4 text-red-500">
          Assembly Failed: {error}
        </div>
      )}

      {/* Success Message */}
      {result && (
        <div className="bg-green-500/10 border border-green-500 rounded-lg p-4 text-green-500">
          Context assembled successfully!
        </div>
      )}

      {/* Result Card */}
      {result && (
        <>
          <ContextResultCard result={result} />

          {/* Raw JSON Expander */}
          <div className="bg-gray-800 border border-gray-700 rounded-lg overflow-hidden">
            <button
              onClick={() => setShowRawJson(!showRawJson)}
              className="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-gray-700/50 transition"
            >
              <span className="text-gray-200 font-medium">Raw JSON</span>
              <svg
                className={`w-5 h-5 text-gray-400 transform transition-transform ${
                  showRawJson ? 'rotate-180' : ''
                }`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M19 9l-7 7-7-7"
                />
              </svg>
            </button>
            {showRawJson && (
              <div className="border-t border-gray-700 p-4">
                <JsonViewer data={result} maxHeight="400px" />
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
