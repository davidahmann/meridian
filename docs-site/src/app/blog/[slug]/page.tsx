import { getDocContent, getAllDocSlugs } from '@/lib/docs';
import { markdownToHtml } from '@/lib/markdown';
import { notFound } from 'next/navigation';
import { Metadata } from 'next';
import MarkdownRenderer from '@/components/MarkdownRenderer';
import Faq from '@/components/Faq';
import { canonicalUrl } from '@/lib/site';

interface PageProps {
  params: Promise<{ slug: string }>;
}

export async function generateStaticParams() {
  const slugs = getAllDocSlugs();
  // Get only blog posts
  return slugs
    .filter((slug) => slug.startsWith('blog/'))
    .map((slug) => ({
      slug: slug.replace('blog/', ''),
    }));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug } = await params;
  const doc = getDocContent(`blog/${slug}`);

  const title = doc?.frontmatter?.title || slug.replace(/-/g, ' ');
  const canonical = canonicalUrl(`/blog/${slug}/`);

  return {
    title: `${title} - Fabra Blog`,
    description: doc?.frontmatter?.description || 'Fabra blog post',
    keywords: doc?.frontmatter?.keywords,
    alternates: {
      canonical,
    },
    openGraph: {
      title: `${title} - Fabra Blog`,
      description: doc?.frontmatter?.description || 'Fabra blog post',
      url: canonical,
      type: 'article',
    },
    twitter: {
      title: `${title} - Fabra Blog`,
      description: doc?.frontmatter?.description || 'Fabra blog post',
    },
  };
}

export default async function BlogPostPage({ params }: PageProps) {
  const { slug } = await params;
  const doc = getDocContent(`blog/${slug}`);

  if (!doc) {
    notFound();
  }

  const html = markdownToHtml(doc.content);
  const faq = doc.frontmatter?.faq ?? [];
  const canonical = canonicalUrl(`/blog/${slug}/`);

  return (
    <>
      <MarkdownRenderer html={html} />
      <Faq items={faq} canonical={canonical} />
    </>
  );
}
