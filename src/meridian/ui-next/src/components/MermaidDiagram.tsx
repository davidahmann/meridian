'use client';

import { useEffect, useRef } from 'react';

interface MermaidDiagramProps {
  code: string;
}

export default function MermaidDiagram({ code }: MermaidDiagramProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const renderDiagram = async () => {
      if (!containerRef.current || !code) return;

      // Dynamically import mermaid to avoid SSR issues
      const mermaid = (await import('mermaid')).default;

      mermaid.initialize({
        startOnLoad: false,
        theme: 'dark',
        themeVariables: {
          background: '#111827',
          primaryColor: '#1f2937',
          primaryTextColor: '#f9fafb',
          primaryBorderColor: '#374151',
          lineColor: '#9ca3af',
          secondaryColor: '#374151',
          tertiaryColor: '#1f2937',
        },
        flowchart: {
          useMaxWidth: true,
          htmlLabels: true,
          curve: 'basis',
        },
      });

      try {
        const { svg } = await mermaid.render('mermaid-diagram', code);
        containerRef.current.innerHTML = svg;
      } catch (error) {
        console.error('Mermaid rendering error:', error);
        containerRef.current.innerHTML = `<div class="text-red-500 p-4">Failed to render diagram</div>`;
      }
    };

    renderDiagram();
  }, [code]);

  return (
    <div
      ref={containerRef}
      className="w-full bg-gray-900 rounded-lg p-4 flex items-center justify-center min-h-[300px]"
    />
  );
}
