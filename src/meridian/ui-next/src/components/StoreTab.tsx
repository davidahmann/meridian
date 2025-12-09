'use client';

import { useState } from 'react';
import type { Entity, Feature, FeatureValues } from '@/types/api';
import { getFeatures } from '@/lib/api';
import FeatureCard from './FeatureCard';
import MermaidDiagram from './MermaidDiagram';
import JsonViewer from './JsonViewer';

interface StoreTabProps {
  entities: Entity[];
  features: Feature[];
  mermaidCode: string;
  onlineStoreType: string;
}

export default function StoreTab({
  entities,
  features,
  mermaidCode,
  onlineStoreType,
}: StoreTabProps) {
  const [selectedEntity, setSelectedEntity] = useState<string>(
    entities[0]?.name || ''
  );
  const [entityId, setEntityId] = useState('u1');
  const [featureValues, setFeatureValues] = useState<FeatureValues | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showDiagram, setShowDiagram] = useState(true);
  const [showDetails, setShowDetails] = useState(false);

  const selectedEntityObj = entities.find((e) => e.name === selectedEntity);
  const entityFeatures = features.filter((f) => f.entity === selectedEntity);

  const handleFetchFeatures = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const values = await getFeatures(selectedEntity, entityId);
      setFeatureValues(values);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to fetch features');
    } finally {
      setIsLoading(false);
    }
  };

  if (entities.length === 0) {
    return (
      <div className="bg-amber-500/10 border border-amber-500 rounded-lg p-4 text-amber-500">
        No entities found in the Feature Store.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Feature System Map */}
      <div className="bg-gray-800 border border-gray-700 rounded-lg overflow-hidden">
        <button
          onClick={() => setShowDiagram(!showDiagram)}
          className="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-gray-700/50 transition"
        >
          <span className="text-gray-200 font-medium">Feature System Map</span>
          <svg
            className={`w-5 h-5 text-gray-400 transform transition-transform ${
              showDiagram ? 'rotate-180' : ''
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
        {showDiagram && (
          <div className="border-t border-gray-700">
            <MermaidDiagram code={mermaidCode} />
          </div>
        )}
      </div>

      {/* Entity Selector */}
      <div>
        <label className="block text-sm font-medium text-gray-400 mb-2">
          Select Entity
        </label>
        <select
          value={selectedEntity}
          onChange={(e) => {
            setSelectedEntity(e.target.value);
            setFeatureValues(null);
          }}
          className="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-2 text-gray-100 focus:border-green-500 focus:ring-1 focus:ring-green-500 outline-none"
        >
          {entities.map((entity) => (
            <option key={entity.name} value={entity.name}>
              {entity.name}
            </option>
          ))}
        </select>
      </div>

      {/* Entity Info Card */}
      {selectedEntityObj && (
        <div className="bg-gray-800 border border-gray-700 rounded-lg p-5">
          <h3 className="text-gray-100 text-lg font-semibold mb-2">
            Entity: {selectedEntityObj.name}
          </h3>
          <div className="text-gray-400">
            <span className="text-green-500 font-mono">id_column:</span>{' '}
            {selectedEntityObj.id_column}
          </div>
          {selectedEntityObj.description && (
            <div className="text-gray-500 italic mt-2">
              {selectedEntityObj.description}
            </div>
          )}
        </div>
      )}

      {/* Entity ID Input */}
      <div>
        <label className="block text-sm font-medium text-gray-400 mb-2">
          Enter {selectedEntityObj?.id_column || 'Entity ID'}
        </label>
        <input
          type="text"
          value={entityId}
          onChange={(e) => setEntityId(e.target.value)}
          className="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-2 text-gray-100 focus:border-green-500 focus:ring-1 focus:ring-green-500 outline-none"
          placeholder="Enter entity ID..."
        />
      </div>

      {/* Fetch Button */}
      <button
        onClick={handleFetchFeatures}
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
            Fetching...
          </>
        ) : (
          <>
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            Fetch Features
          </>
        )}
      </button>

      {/* Error Message */}
      {error && (
        <div className="bg-red-500/10 border border-red-500 rounded-lg p-4 text-red-500">
          {error}
        </div>
      )}

      {/* Feature Values */}
      {featureValues && (
        <>
          <h3 className="text-xl font-semibold text-gray-100 mt-6">
            Feature Values
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {entityFeatures.map((feature) => (
              <FeatureCard
                key={feature.name}
                feature={feature}
                value={featureValues[feature.name]}
              />
            ))}
          </div>

          {/* Feature Details Expander */}
          <div className="bg-gray-800 border border-gray-700 rounded-lg overflow-hidden mt-4">
            <button
              onClick={() => setShowDetails(!showDetails)}
              className="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-gray-700/50 transition"
            >
              <span className="text-gray-200 font-medium">
                Feature Definition Details
              </span>
              <svg
                className={`w-5 h-5 text-gray-400 transform transition-transform ${
                  showDetails ? 'rotate-180' : ''
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
            {showDetails && (
              <div className="border-t border-gray-700 p-4">
                <JsonViewer
                  data={entityFeatures.map((f) => ({
                    name: f.name,
                    refresh: f.refresh || null,
                    ttl: f.ttl || null,
                    materialize: f.materialize,
                  }))}
                  maxHeight="300px"
                />
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
