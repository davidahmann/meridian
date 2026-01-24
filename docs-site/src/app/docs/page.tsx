import { getDocContent } from '@/lib/docs';
import { markdownToHtml } from '@/lib/markdown';
import { notFound } from 'next/navigation';
import { Metadata } from 'next';
import MarkdownRenderer from '@/components/MarkdownRenderer';
import Faq from '@/components/Faq';
import { canonicalUrl } from '@/lib/site';

export const metadata: Metadata = {
  title: 'Documentation - Fabra',
  description: 'Fabra documentation - Context Infrastructure for AI Applications',
  alternates: {
    canonical: canonicalUrl('/docs/'),
  },
};

export default function DocsIndexPage() {
  const doc = getDocContent('index');

  if (!doc) {
    notFound();
  }

  const html = markdownToHtml(doc.content);
  const faq = doc.frontmatter?.faq ?? [];

  return (
    <>
      <MarkdownRenderer html={html} />
      <Faq items={faq} canonical={canonicalUrl('/docs/')} />
    </>
  );
}
