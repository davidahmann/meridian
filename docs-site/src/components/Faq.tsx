import React from 'react';

type FaqItem = { q: string; a: string };

export default function Faq({
  items,
  canonical,
}: {
  items: FaqItem[];
  canonical: string;
}) {
  if (!items.length) return null;

  const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: items.map((item) => ({
      '@type': 'Question',
      name: item.q,
      acceptedAnswer: {
        '@type': 'Answer',
        text: item.a,
      },
    })),
  };

  return (
    <section className="not-prose mt-12 border-t border-gray-800 pt-10">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />

      <div className="flex items-baseline justify-between gap-4">
        <h2 className="text-xl font-semibold text-white">FAQ</h2>
        <a
          href={canonical}
          className="text-sm text-gray-400 hover:text-gray-200 underline underline-offset-4"
        >
          Link
        </a>
      </div>

      <dl className="mt-6 space-y-6">
        {items.map((item, idx) => (
          <div key={idx} className="rounded-lg border border-gray-800 bg-gray-900/40 p-4">
            <dt className="text-sm font-semibold text-gray-100">{item.q}</dt>
            <dd className="mt-2 text-sm text-gray-300">{item.a}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
