import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import 'highlight.js/lib/languages/python'
import 'highlight.js/lib/languages/r'
import 'highlight.js/lib/languages/bash'
import 'highlight.js/lib/languages/javascript'
import 'highlight.js/lib/languages/typescript'
import 'highlight.js/lib/languages/json'
import 'highlight.js/lib/languages/yaml'
import 'highlight.js/lib/languages/markdown'
import 'highlight.js/lib/languages/latex'
import { clsx } from 'clsx'
import { Copy, Check } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from '@/i18n'

interface MarkdownRendererProps {
  content: string
  className?: string
}

function CodeBlock({ language, value }: { language?: string; value: string }) {
  const { t } = useTranslation()
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(value)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="my-3 overflow-hidden rounded-lg border border-border bg-card">
      <div className="flex items-center justify-between border-b border-border bg-muted px-3 py-1.5">
        <span className="text-xs font-medium text-muted-foreground">{language || 'text'}</span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 rounded px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
          {copied ? t('common.copied') : t('common.copy')}
        </button>
      </div>
      <pre className="overflow-x-auto p-4 text-xs leading-relaxed">
        <code className={`language-${language || 'text'}`}>{value}</code>
      </pre>
    </div>
  )
}

export function MarkdownRenderer({ content, className }: MarkdownRendererProps) {
  return (
    <div className={clsx('prose prose-sm max-w-none dark:prose-invert', className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={{
          code({ inline, className, children, ...props }: any) {
            const match = /language-(\w+)/.exec(className || '')
            const value = String(children).replace(/\n$/, '')
            if (!inline && match) {
              return <CodeBlock language={match[1]} value={value} />
            }
            return (
              <code className={className} {...props}>
                {children}
              </code>
            )
          },
          table({ children }) {
            return (
              <div className="my-3 overflow-x-auto rounded-lg border border-border">
                <table className="min-w-full text-sm">{children}</table>
              </div>
            )
          },
          thead({ children }) {
            return <thead className="bg-muted">{children}</thead>
          },
          th({ children }) {
            return <th className="px-3 py-2 text-left font-semibold">{children}</th>
          },
          td({ children }) {
            return <td className="border-t border-border px-3 py-2">{children}</td>
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
