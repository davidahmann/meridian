import type {
  StoreInfo,
  FeatureValues,
  ContextResult,
  MermaidGraph,
} from '@/types/api';

const API_BASE = '/api';

async function fetchAPI<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `API error: ${res.status}`);
  }

  return res.json();
}

export async function getStoreInfo(): Promise<StoreInfo> {
  return fetchAPI<StoreInfo>('/store');
}

export async function getFeatures(
  entityName: string,
  entityId: string
): Promise<FeatureValues> {
  return fetchAPI<FeatureValues>(
    `/features/${encodeURIComponent(entityName)}/${encodeURIComponent(entityId)}`
  );
}

export async function assembleContext(
  contextName: string,
  params: Record<string, string>
): Promise<ContextResult> {
  return fetchAPI<ContextResult>(`/context/${encodeURIComponent(contextName)}`, {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

export async function getMermaidGraph(): Promise<MermaidGraph> {
  return fetchAPI<MermaidGraph>('/graph');
}
