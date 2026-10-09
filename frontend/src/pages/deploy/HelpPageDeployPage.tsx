import { useEffect, useMemo, useState } from 'react';
import { Check, Copy, Loader2, Plus, X } from 'lucide-react';
import { cn } from '../../lib/utils';
import { useDeploy } from './DeployProvider';

const SLUG_RE = /^[a-z0-9](?:[a-z0-9-]{1,46}[a-z0-9])$/;

function slugify(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9-]+/g, '-').replace(/-{2,}/g, '-').replace(/^-|-$/g, '');
}

function helpPageUrl(slug: string) {
  return `${window.location.origin}/help/${slug}`;
}

function CopyField({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div>
      <p className="mb-1.5 text-sm font-medium text-zinc-900">{label}</p>
      <div className="flex items-start gap-2 rounded-lg border border-hairline bg-zinc-50 p-3">
        <code className="min-w-0 flex-1 whitespace-pre-wrap break-all font-mono text-xs leading-relaxed text-zinc-700">{value}</code>
        <button
          type="button"
          onClick={() => {
            navigator.clipboard.writeText(value).then(() => {
              setCopied(true);
              setTimeout(() => setCopied(false), 1500);
            });
          }}
          className="grid h-7 w-7 shrink-0 place-items-center rounded-md text-zinc-500 transition-colors hover:bg-white hover:text-zinc-900"
          aria-label={`Copy ${label}`}
        >
          {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
        </button>
      </div>
    </div>
  );
}

export default function HelpPageDeployPage() {
  const { deployment, displayName, logoImage, saveHelpPage, isLoading } = useDeploy();

  const [enabled, setEnabled] = useState(false);
  const [slug, setSlug] = useState('');
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setEnabled(deployment.help_page_enabled);
    setSlug(deployment.help_page_slug);
    setTitle(deployment.help_page_title);
    setDescription(deployment.help_page_description);
    setSuggestions(deployment.help_page_suggestions.length ? deployment.help_page_suggestions : []);
  }, [
    deployment.help_page_enabled,
    deployment.help_page_slug,
    deployment.help_page_title,
    deployment.help_page_description,
    deployment.help_page_suggestions,
  ]);

  const cleanSuggestions = suggestions.map((s) => s.trim()).filter(Boolean);
  const isDirty =
    enabled !== deployment.help_page_enabled ||
    slug !== deployment.help_page_slug ||
    title !== deployment.help_page_title ||
    description !== deployment.help_page_description ||
    JSON.stringify(cleanSuggestions) !== JSON.stringify(deployment.help_page_suggestions);
  const slugError = slug && !SLUG_RE.test(slug) ? '3–48 characters: lowercase letters, numbers, and dashes.' : '';

  const liveUrl = deployment.help_page_slug ? helpPageUrl(deployment.help_page_slug) : '';
  const iframeSnippet = useMemo(
    () => (liveUrl ? `<iframe src="${liveUrl}" style="width:100%;height:100vh;border:0" allow="clipboard-write"></iframe>` : ''),
    [liveUrl]
  );

  async function save(nextEnabled = enabled) {
    if (slugError) return;
    setSaving(true);
    const patch: Parameters<typeof saveHelpPage>[0] = {
      help_page_enabled: nextEnabled,
      help_page_title: title,
      help_page_description: description,
      help_page_suggestions: cleanSuggestions,
    };
    if (slug) patch.help_page_slug = slug;
    const ok = await saveHelpPage(patch);
    if (!ok) setEnabled(deployment.help_page_enabled);
    setSaving(false);
  }

  const previewTitle = title.trim() || `How can ${displayName} help?`;

  return (
    <div className="overflow-hidden rounded-2xl border border-hairline bg-white">
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_1.05fr]">
        <div className="space-y-7 border-b border-hairline p-6 md:p-8 lg:border-b-0 lg:border-r">
          {/* Status */}
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold tracking-tight text-zinc-950">Help page</h2>
              <p className="mt-1 text-sm leading-relaxed text-zinc-500">
                A full-page chat you embed at <code className="font-mono text-[12px]">/help</code> on your own site.
              </p>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={enabled}
              disabled={isLoading || saving}
              onClick={() => {
                const next = !enabled;
                setEnabled(next);
                save(next);
              }}
              className={cn(
                'relative h-6 w-11 shrink-0 rounded-full transition-colors disabled:opacity-50',
                enabled ? 'bg-zinc-950' : 'bg-zinc-200'
              )}
            >
              <span className={cn('absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all', enabled ? 'left-[22px]' : 'left-0.5')} />
            </button>
          </div>

          {/* URL */}
          <div>
            <label className="mb-1.5 block text-sm font-medium text-zinc-900" htmlFor="help-slug">Page ID</label>
            <div className={cn('flex items-center overflow-hidden rounded-lg border bg-white focus-within:ring-2 focus-within:ring-zinc-900/10', slugError ? 'border-rose-300' : 'border-hairline')}>
              <span className="shrink-0 border-r border-hairline bg-zinc-50 px-3 py-2 text-sm text-zinc-500">{window.location.host}/help/</span>
              <input
                id="help-slug"
                value={slug}
                onChange={(e) => setSlug(slugify(e.target.value))}
                placeholder="auto-generated"
                className="min-w-0 flex-1 bg-transparent px-3 py-2 text-sm text-zinc-900 outline-none"
              />
            </div>
            {slugError && <p className="mt-1.5 text-xs text-rose-600">{slugError}</p>}
          </div>

          {/* Content */}
          <div>
            <label className="mb-1.5 block text-sm font-medium text-zinc-900" htmlFor="help-title">Headline</label>
            <input
              id="help-title"
              value={title}
              maxLength={120}
              onChange={(e) => setTitle(e.target.value)}
              placeholder={`How can ${displayName} help?`}
              className="w-full rounded-lg border border-hairline px-3 py-2 text-sm text-zinc-900 outline-none focus:ring-2 focus:ring-zinc-900/10"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-zinc-900" htmlFor="help-desc">Description</label>
            <textarea
              id="help-desc"
              value={description}
              maxLength={300}
              rows={2}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Ask anything about our product, billing, or your account."
              className="w-full resize-none rounded-lg border border-hairline px-3 py-2 text-sm text-zinc-900 outline-none focus:ring-2 focus:ring-zinc-900/10"
            />
          </div>

          <div>
            <p className="text-sm font-medium text-zinc-900">Suggested questions</p>
            <p className="mb-2 mt-0.5 text-xs text-zinc-500">Shown as quick replies in the help page and your widget.</p>
            <div className="space-y-2">
              {suggestions.map((s, i) => (
                <div key={i} className="flex items-center gap-2">
                  <input
                    value={s}
                    maxLength={120}
                    onChange={(e) => setSuggestions((cur) => cur.map((v, idx) => (idx === i ? e.target.value : v)))}
                    placeholder="e.g. How do I reset my password?"
                    className="min-w-0 flex-1 rounded-lg border border-hairline px-3 py-2 text-sm text-zinc-900 outline-none focus:ring-2 focus:ring-zinc-900/10"
                  />
                  <button
                    type="button"
                    onClick={() => setSuggestions((cur) => cur.filter((_, idx) => idx !== i))}
                    className="grid h-9 w-9 shrink-0 place-items-center rounded-lg text-zinc-400 hover:bg-zinc-100 hover:text-zinc-900"
                    aria-label="Remove question"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              ))}
              {suggestions.length < 4 && (
                <button
                  type="button"
                  onClick={() => setSuggestions((cur) => [...cur, ''])}
                  className="inline-flex items-center gap-1.5 text-sm font-medium text-zinc-600 hover:text-zinc-950"
                >
                  <Plus className="h-4 w-4" /> Add question
                </button>
              )}
            </div>
          </div>

          <div className="flex items-center justify-end gap-2 border-t border-hairline pt-5">
            <button
              type="button"
              onClick={() => save()}
              disabled={!isDirty || saving || !!slugError}
              className="inline-flex h-9 items-center gap-2 rounded-lg bg-zinc-950 px-4 text-sm font-medium text-white transition-colors hover:bg-zinc-800 disabled:opacity-40"
            >
              {saving && <Loader2 className="h-4 w-4 animate-spin" />} Save changes
            </button>
          </div>

          {/* Install */}
          <div className="space-y-4 border-t border-hairline pt-6">
            <div>
              <h3 className="text-sm font-semibold text-zinc-950">Add it to your site</h3>
              <ol className="mt-2 list-decimal space-y-1 pl-4 text-sm leading-relaxed text-zinc-500">
                <li>Create a page at <code className="font-mono text-[12px]">yoursite.com/help</code>.</li>
                <li>Paste this snippet as the page's only content.</li>
                <li>Make sure your domain is in the widget's allowed domains.</li>
              </ol>
            </div>
            {deployment.help_page_enabled && iframeSnippet ? (
              <CopyField label="Embed code" value={iframeSnippet} />
            ) : (
              <p className="rounded-lg border border-dashed border-hairline px-4 py-3 text-sm text-zinc-500">
                Turn the help page on to get your embed code.
              </p>
            )}
          </div>
        </div>

        {/* Live preview */}
        <div className="relative overflow-hidden bg-zinc-50 p-6 md:p-10">
          <div className="absolute inset-0 bg-[radial-gradient(#e4e4e7_1px,transparent_1px)] [background-size:14px_14px] opacity-60" aria-hidden />
          <div className="relative mx-auto max-w-md overflow-hidden rounded-xl border border-hairline bg-white shadow-soft">
            <div className="flex items-center gap-1.5 border-b border-hairline bg-zinc-50 px-3 py-2">
              <span className="h-2 w-2 rounded-full bg-zinc-300" />
              <span className="h-2 w-2 rounded-full bg-zinc-300" />
              <span className="h-2 w-2 rounded-full bg-zinc-300" />
              <span className="ml-2 truncate rounded bg-white px-2 py-0.5 text-[10px] text-zinc-500">
                {window.location.host}/help/{slug || '…'}
              </span>
            </div>
            <div className="flex h-11 items-center gap-2 bg-zinc-950 px-4 text-white">
              <span className="grid h-6 w-6 place-items-center overflow-hidden rounded-md bg-white/15 text-[9px] font-semibold">
                {logoImage ? <img src={logoImage} alt="" className="h-full w-full object-cover" /> : displayName.slice(0, 2).toUpperCase()}
              </span>
              <span className="text-xs font-medium">{displayName}</span>
            </div>
            <div className="flex min-h-[300px] flex-col p-4">
              <div className="w-fit max-w-[85%] rounded-2xl bg-zinc-100 px-3.5 py-2.5 text-xs leading-relaxed text-zinc-900">
                <p className="font-medium">{previewTitle}</p>
                {description.trim() && <p className="mt-1 text-zinc-600">{description}</p>}
              </div>
              <div className="mt-auto flex flex-wrap justify-end gap-1.5 pt-6">
                {cleanSuggestions.map((s) => (
                  <span key={s} className="rounded-full border border-hairline px-3 py-1.5 text-[11px] text-zinc-700">{s}</span>
                ))}
              </div>
              <p className="py-2 text-center text-[10px] text-zinc-400">Powered by HelpdeskAI</p>
              <div className="flex items-center gap-2 rounded-full border-[1.5px] border-zinc-300 py-1 pl-3.5 pr-1">
                <span className="flex-1 text-[11px] text-zinc-400">Ask me anything…</span>
                <span className="grid h-6 w-6 place-items-center rounded-full bg-zinc-950" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
