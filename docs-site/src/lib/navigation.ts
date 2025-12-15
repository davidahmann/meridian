export interface NavItem {
  title: string;
  href: string;
  children?: NavItem[];
}

export const navigation: NavItem[] = [
  {
    title: 'Getting Started',
    href: '/docs',
    children: [
      { title: 'Introduction', href: '/docs' },
      { title: 'Quickstart', href: '/docs/quickstart' },
      { title: 'How It Works', href: '/docs/how-it-works' },
      { title: 'Incident Playbook', href: '/docs/incident-playbook' },
      { title: 'Replay Guarantees', href: '/docs/replay-guarantees' },
      { title: 'Philosophy', href: '/docs/philosophy' },
      { title: 'Architecture', href: '/docs/architecture' },
      { title: 'Why We Built Fabra', href: '/docs/why-we-built-fabra' },
    ],
  },
  {
    title: 'For ML Engineers',
    href: '/docs/feature-store-without-kubernetes',
    children: [
      { title: 'Feature Store Without K8s', href: '/docs/feature-store-without-kubernetes' },
      { title: 'Fabra vs Feast', href: '/docs/feast-alternative' },
      { title: 'Hybrid Features', href: '/docs/hybrid-features' },
      { title: 'Event-Driven Features', href: '/docs/event-driven-features' },
      { title: 'Events & Workers', href: '/docs/events-and-workers' },
      { title: 'Hooks', href: '/docs/hooks' },
    ],
  },
  {
    title: 'For AI Engineers',
    href: '/docs/context-store',
    children: [
      { title: 'Context Store', href: '/docs/context-store' },
      { title: 'Context Records (CRS-001)', href: '/docs/context-record-spec' },
      { title: 'Integrity & Verification', href: '/docs/integrity-and-verification' },
      { title: 'Exporters & Adapters', href: '/docs/exporters-and-adapters' },
      { title: 'Context Assembly', href: '/docs/context-assembly' },
      { title: 'Token Budget Management', href: '/docs/token-budget-management' },
      { title: 'Retrievers', href: '/docs/retrievers' },
      { title: 'Context Accountability', href: '/docs/context-accountability' },
      { title: 'Freshness SLAs', href: '/docs/freshness-sla' },
      { title: 'RAG Audit Trail', href: '/docs/rag-audit-trail' },
    ],
  },
  {
    title: 'Deployment',
    href: '/docs/local-to-production',
    children: [
      { title: 'Local to Production', href: '/docs/local-to-production' },
      { title: 'WebUI Dashboard', href: '/docs/webui' },
      { title: 'Compliance Guide', href: '/docs/compliance-guide' },
      { title: 'Unit Testing', href: '/docs/unit_testing' },
      { title: 'Troubleshooting', href: '/docs/troubleshooting' },
    ],
  },
  {
    title: 'Use Cases',
    href: '/docs/use-cases/rag-chatbot',
    children: [
      { title: 'RAG Chatbot', href: '/docs/use-cases/rag-chatbot' },
      { title: 'Fraud Detection', href: '/docs/use-cases/fraud-detection' },
      { title: 'Churn Prediction', href: '/docs/use-cases/churn-prediction' },
      { title: 'Real-Time Recommendations', href: '/docs/use-cases/real-time-recommendations' },
    ],
  },
  {
    title: 'Reference',
    href: '/docs/comparisons',
    children: [
      { title: 'Comparisons', href: '/docs/comparisons' },
      { title: 'Glossary', href: '/docs/glossary' },
      { title: 'FAQ', href: '/docs/faq' },
      { title: 'Changelog', href: '/docs/changelog' },
    ],
  },
  {
    title: 'Blog',
    href: '/blog',
    children: [
      { title: 'Why We Built a Feast Alternative', href: '/blog/feast-alternative' },
      { title: 'Feast Too Complex', href: '/blog/feast-too-complex' },
      { title: 'RAG Without LangChain', href: '/blog/rag-without-langchain' },
      { title: 'Context Assembly', href: '/blog/context-assembly' },
      { title: 'Context Replay', href: '/blog/context-replay' },
      { title: 'Token Budget Management', href: '/blog/token-budget-management' },
      { title: 'Freshness Guarantees', href: '/blog/freshness-guarantees' },
      { title: 'AI Audit Trail', href: '/blog/ai-audit-trail' },
      { title: 'Deploy Without Kubernetes', href: '/blog/deploy-without-kubernetes' },
      { title: 'Feature Store for Startups', href: '/blog/feature-store-for-startups' },
      { title: 'Local Feature Store', href: '/blog/local-feature-store' },
      { title: 'pgvector vs Pinecone', href: '/blog/pgvector-vs-pinecone' },
      { title: 'Point-in-Time Features', href: '/blog/point-in-time-features' },
      { title: 'Python Decorators for ML', href: '/blog/python-decorators-ml' },
      { title: 'Fabra vs Context Platforms', href: '/blog/fabra-vs-context-platforms' },
      { title: 'RAG Compliance: Fintech', href: '/blog/rag-compliance-fintech' },
      { title: 'RAG Compliance: Healthcare', href: '/blog/rag-compliance-healthcare' },
    ],
  },
];
