import { getDocContent, getAllDocSlugs } from '@/lib/docs';
import { markdownToHtml } from '@/lib/markdown';
import { notFound } from 'next/navigation';
import { Metadata } from 'next';
import MarkdownRenderer from '@/components/MarkdownRenderer';
import Faq from '@/components/Faq';
import { canonicalUrl } from '@/lib/site';

interface PageProps {
  params: Promise<{ slug: string[] }>;
}

export async function generateStaticParams() {
  const slugs = getAllDocSlugs();
  // Filter out blog posts (they have their own route at /blog/[slug])
  // and filter out index.md (handled by /docs/page.tsx)
  return slugs
    .filter((slug) => !slug.startsWith('blog/') && slug !== 'index')
    .map((slug) => ({
      slug: slug.split('/'),
    }));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug } = await params;
  const slugPath = slug.join('/');
  const doc = getDocContent(slugPath);

  const title = doc?.frontmatter?.title || slugPath.split('/').pop()?.replace(/-|_/g, ' ') || 'Documentation';
  const canonical = canonicalUrl(`/docs/${slugPath}/`);

  return {
    title: `${title} - Fabra`,
    description: doc?.frontmatter?.description || 'Fabra documentation',
    keywords: doc?.frontmatter?.keywords,
    alternates: {
      canonical,
    },
    openGraph: {
      title: `${title} - Fabra`,
      description: doc?.frontmatter?.description || 'Fabra documentation',
      url: canonical,
      type: 'article',
    },
    twitter: {
      title: `${title} - Fabra`,
      description: doc?.frontmatter?.description || 'Fabra documentation',
    },
  };
}

export default async function DocPage({ params }: PageProps) {
  const { slug } = await params;
  const slugPath = slug.join('/');
  const doc = getDocContent(slugPath);

  if (!doc) {
    notFound();
  }

  const html = markdownToHtml(doc.content);
  const faq = doc.frontmatter?.faq ?? [];
  const canonical = canonicalUrl(`/docs/${slugPath}/`);

  return (
    <>
      <MarkdownRenderer html={html} />
      <Faq items={faq} canonical={canonical} />
    </>
  );
}
