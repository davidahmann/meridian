// API response types matching Python backend

export interface Entity {
  name: string;
  id_column: string;
  description?: string;
}

export interface Feature {
  name: string;
  entity: string;
  refresh?: string;
  ttl?: string;
  materialize: boolean;
}

export interface Retriever {
  name: string;
  backend: string;
  cache_ttl: string;
}

export interface ContextDefinition {
  name: string;
  description?: string;
  parameters: ContextParameter[];
}

export interface ContextParameter {
  name: string;
  type: string;
  default?: string;
  required: boolean;
}

export interface ContextResult {
  id: string;
  items: ContextItem[];
  meta: {
    token_usage?: number;
    cost_usd?: number;
    latency_ms?: number;
    freshness_status?: string;
  };
}

export interface ContextItem {
  content: string;
  priority: number;
  source?: string;
}

export interface StoreInfo {
  file_name: string;
  entities: Entity[];
  features: Feature[];
  contexts: ContextDefinition[];
  retrievers: Retriever[];
  online_store_type: string;
}

export interface FeatureValues {
  [key: string]: unknown;
}

export interface MermaidGraph {
  code: string;
}
