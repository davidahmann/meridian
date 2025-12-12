import { marked } from 'marked';

// Configure marked for GitHub Flavored Markdown
marked.setOptions({
  gfm: true, // Enable GitHub Flavored Markdown (tables, strikethrough, etc.)
  breaks: false, // Don't convert \n to <br>
});

// Get basePath for production (GitHub Pages deploys to /fabra/)
const basePath = process.env.NODE_ENV === 'production' ? '/fabra' : '';

// Custom renderer to handle internal .md links and add classes
const renderer = new marked.Renderer();

// Override link rendering to handle internal .md links
renderer.link = function ({ href, title, text }) {
  // Convert internal .md links to proper paths with basePath
  if (href && href.endsWith('.md')) {
    // Remove .md extension
    let path = href.replace('.md', '');

    // Handle relative paths like ../context-accountability.md (from blog posts)
    if (path.startsWith('../')) {
      path = path.replace('../', '');
    }

    // Determine if it's a blog or docs link
    if (path.startsWith('blog/')) {
      // Blog links go to /blog/slug
      href = basePath + '/' + path;
    } else if (path.startsWith('use-cases/')) {
      // Use-cases stay under /docs/use-cases/
      href = basePath + '/docs/' + path;
    } else {
      // Regular docs links
      href = basePath + '/docs/' + path;
    }
  }

  // External links open in new tab
  if (href && (href.startsWith('http://') || href.startsWith('https://'))) {
    return `<a href="${href}" target="_blank" rel="noopener noreferrer"${title ? ` title="${title}"` : ''}>${text}</a>`;
  }

  return `<a href="${href}"${title ? ` title="${title}"` : ''}>${text}</a>`;
};

// Override code block rendering to add language class
renderer.code = function ({ text, lang }) {
  const language = lang || '';
  // Don't escape mermaid code - it needs the raw text for parsing
  if (language === 'mermaid') {
    return `<pre><code class="language-mermaid">${text}</code></pre>`;
  }
  const escapedCode = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  return `<pre><code class="language-${language}">${escapedCode}</code></pre>`;
};

// Override inline code rendering
renderer.codespan = function ({ text }) {
  return `<code class="inline-code">${text}</code>`;
};

// Use the custom renderer
marked.use({ renderer });

/**
 * Convert markdown to HTML using marked library
 * Supports full GitHub Flavored Markdown including tables
 */
export function markdownToHtml(markdown: string): string {
  // Remove frontmatter
  const content = markdown.replace(/^---[\s\S]*?---\n*/m, '');

  // Remove Jekyll liquid tags
  const cleanContent = content
    .replace(/\{%.*?%\}/g, '')
    .replace(/\{\{.*?\}\}/g, '');

  // Parse markdown to HTML
  return marked.parse(cleanContent) as string;
}
