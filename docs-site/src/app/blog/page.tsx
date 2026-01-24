import Link from 'next/link';
import { navigation } from '@/lib/navigation';
import { Metadata } from 'next';
import { canonicalUrl } from '@/lib/site';

export const metadata: Metadata = {
  title: 'Blog - Fabra',
  description: 'Articles about feature stores, context assembly, and AI engineering',
  alternates: {
    canonical: canonicalUrl('/blog/'),
  },
};

export default function BlogIndexPage() {
  const blogSection = navigation.find((section) => section.title === 'Blog');
  const blogPosts = blogSection?.children || [];

  return (
    <div className="prose prose-invert max-w-none">
      <h1>Blog</h1>
      <p className="text-lg text-gray-300">
        Articles about feature stores, context assembly, RAG systems, and AI engineering best practices.
      </p>
      <div className="mt-8 grid gap-4">
        {blogPosts.map((post) => (
          <Link
            key={post.href}
            href={post.href}
            className="block p-4 rounded-lg border border-gray-700 hover:border-cyan-500 hover:bg-gray-800/50 transition-colors no-underline"
          >
            <h3 className="text-lg font-semibold text-white m-0">{post.title}</h3>
          </Link>
        ))}
      </div>
    </div>
  );
}
