'use client';

interface JsonViewerProps {
  data: unknown;
  maxHeight?: string;
}

export default function JsonViewer({ data, maxHeight = '400px' }: JsonViewerProps) {
  const jsonStr = JSON.stringify(data, null, 2);

  return (
    <div
      className="bg-gray-700 border border-gray-600 rounded-lg p-4 overflow-auto"
      style={{ maxHeight }}
    >
      <pre className="text-gray-300 text-sm font-mono whitespace-pre-wrap break-words m-0">
        {jsonStr}
      </pre>
    </div>
  );
}
