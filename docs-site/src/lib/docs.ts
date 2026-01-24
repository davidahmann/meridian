import fs from 'fs';
import path from 'path';
import matter from 'gray-matter';

const docsDirectory = path.join(process.cwd(), '..', 'docs');

export interface DocContent {
  content: string;
  frontmatter: {
    title?: string;
    description?: string;
    keywords?: string;
    faq?: Array<{
      q: string;
      a: string;
    }>;
  };
}

export function getDocContent(slug: string): DocContent | null {
  // Try different file paths
  const possiblePaths = [
    path.join(docsDirectory, `${slug}.md`),
    path.join(docsDirectory, slug, 'index.md'),
  ];

  for (const filePath of possiblePaths) {
    if (fs.existsSync(filePath)) {
      const fileContents = fs.readFileSync(filePath, 'utf8');
      const { data, content } = matter(fileContents);

      // Clean up the markdown content
      // Remove Jekyll-specific frontmatter liquid tags
      const cleanContent = content
        .replace(/\{%.*?%\}/g, '')
        .replace(/\{\{.*?\}\}/g, '');

      return {
        content: cleanContent,
        frontmatter: data as DocContent['frontmatter'],
      };
    }
  }

  return null;
}

export function getAllDocSlugs(): string[] {
  const slugs: string[] = [];

  function walkDir(dir: string, prefix: string = '') {
    const files = fs.readdirSync(dir);

    for (const file of files) {
      const filePath = path.join(dir, file);
      const stat = fs.statSync(filePath);

      if (stat.isDirectory()) {
        walkDir(filePath, path.join(prefix, file));
      } else if (file.endsWith('.md') && !file.startsWith('_')) {
        const slug = path.join(prefix, file.replace('.md', ''));
        slugs.push(slug);
      }
    }
  }

  if (fs.existsSync(docsDirectory)) {
    walkDir(docsDirectory);
  }

  return slugs;
}
