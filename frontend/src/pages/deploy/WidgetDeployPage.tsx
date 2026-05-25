import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  BookOpen,
  Camera,
  Code2,
  Copy,
  Globe,
  Loader2,
  MessageCircle,
  Plus,
  RefreshCw,
  Shield,
  X,
} from 'lucide-react';
import { AgentAvatar } from '../../components/deploy/AgentAvatar';
import { WidgetLivePreview } from '../../components/deploy/WidgetLivePreview';
import { cn } from '../../lib/utils';
import { useDeploy } from './DeployProvider';

export default function WidgetDeployPage() {
  const [copied, setCopied] = useState(false);
  const {
    agent,
    deployment,
    domains,
    domainDraft,
    setDomainDraft,
    isAddingDomain,
    setIsAddingDomain,
    isSaving,
    displayName,
    previewGreeting,
    embedCode,
    logoImage,
    updateDeployment,
    addDomain,
    removeDomain,
    updateInitialMessage,
    removeInitialMessage,
    addInitialMessage,
    regenerateDeploymentId,
    uploadLogo,
    isUploadingLogo,
  } = useDeploy();

  async function copyEmbed() {
    await navigator.clipboard?.writeText(embedCode);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1400);
  }

  const previewMessages = deployment.initial_messages.filter((m) => m.trim());

  return (
    <section className="overflow-hidden rounded-2xl border border-surface-container-highest bg-surface-container-lowest shadow-sm">
        <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,420px)_1fr]">
          <div className="space-y-6 border-b border-surface-container-highest p-6 xl:border-b-0 xl:border-r">
            <div className="flex items-center gap-3">
              <div className="grid h-11 w-11 place-items-center rounded-xl bg-sky-500 text-white">
                <MessageCircle className="h-5 w-5" />
              </div>
              <div>
                <h2 className="text-lg font-bold text-brand-primary">Widget settings</h2>
                <p className="text-xs text-on-surface-variant">Appearance, messages, and security.</p>
              </div>
            </div>

            <label className="block space-y-2">
              <span className="text-xs font-bold uppercase tracking-widest text-on-surface-variant">
                Display name
              </span>
              <input
                value={deployment.display_name}
                onChange={(e) => updateDeployment({ display_name: e.target.value })}
                className="h-11 w-full rounded-lg border border-surface-container-highest bg-surface-container-low px-4 text-sm focus:border-brand-primary focus:outline-none focus:ring-1 focus:ring-brand-primary/20"
              />
            </label>

            <div className="space-y-3">
              <span className="text-xs font-bold uppercase tracking-widest text-on-surface-variant">
                Display logo
              </span>
              <div className="flex items-center gap-4">
                <label className="group relative shrink-0 cursor-pointer">
                  <input
                    type="file"
                    accept="image/png,image/jpeg,image/webp,image/svg+xml"
                    className="hidden"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) uploadLogo(file);
                      e.target.value = '';
                    }}
                  />
                  <div className="relative h-20 w-20 overflow-hidden rounded-full border-2 border-surface-container-highest bg-surface-container-low shadow-sm transition-all group-hover:border-brand-primary/40 group-hover:ring-2 group-hover:ring-brand-primary/10">
                    {logoImage ? (
                      <img src={logoImage} alt="" className="h-full w-full object-cover" />
                    ) : (
                      <div className="flex h-full w-full items-center justify-center bg-brand-primary text-lg font-black text-brand-on-primary">
                        <AgentAvatar name={displayName} />
                      </div>
                    )}
                    <div className="absolute inset-0 flex items-center justify-center bg-zinc-950/45 opacity-0 transition-opacity group-hover:opacity-100">
                      {isUploadingLogo ? (
                        <Loader2 className="h-5 w-5 animate-spin text-white" />
                      ) : (
                        <Camera className="h-5 w-5 text-white" />
                      )}
                    </div>
                  </div>
                </label>
                <div className="min-w-0">
                  <p className="text-sm font-bold text-brand-primary">Widget avatar</p>
                  <p className="mt-1 text-xs leading-relaxed text-on-surface-variant">
                    {isUploadingLogo
                      ? 'Uploading...'
                      : 'Click the photo to upload a new image (PNG, JPG, WEBP, or SVG).'}
                  </p>
                </div>
              </div>
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-widest text-on-surface-variant">
                  Initial messages
                </span>
                <button
                  type="button"
                  onClick={addInitialMessage}
                  className="inline-flex items-center gap-1 text-xs font-bold text-brand-primary"
                >
                  <Plus className="h-3.5 w-3.5" />
                  Add
                </button>
              </div>
              {deployment.initial_messages.map((message, index) => (
                <div key={index} className="flex gap-2">
                  <input
                    value={message}
                    onChange={(e) => updateInitialMessage(index, e.target.value)}
                    className="h-11 min-w-0 flex-1 rounded-lg border border-surface-container-highest bg-surface-container-low px-4 text-sm focus:border-brand-primary focus:outline-none"
                  />
                  <button
                    type="button"
                    onClick={() => removeInitialMessage(index)}
                    className="grid h-11 w-11 place-items-center rounded-lg border border-surface-container-highest bg-surface-container-low text-on-surface-variant hover:text-rose-600"
                    aria-label="Remove message"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              ))}
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <span className="text-xs font-bold uppercase tracking-widest text-on-surface-variant">Style</span>
                <div className="grid grid-cols-2 rounded-lg border border-surface-container-highest bg-surface-container-low p-1">
                  {(['dark', 'light'] as const).map((theme) => (
                    <button
                      key={theme}
                      type="button"
                      onClick={() => updateDeployment({ theme })}
                      className={cn(
                        'h-9 rounded-md text-sm font-bold capitalize',
                        deployment.theme === theme
                          ? 'bg-brand-primary text-brand-on-primary'
                          : 'text-on-surface-variant'
                      )}
                    >
                      {theme}
                    </button>
                  ))}
                </div>
              </div>
              <label className="space-y-2">
                <span className="text-xs font-bold uppercase tracking-widest text-on-surface-variant">
                  Primary color
                </span>
                <div className="flex h-11 items-center gap-3 rounded-lg border border-surface-container-highest bg-surface-container-low px-3">
                  <input
                    type="color"
                    value={deployment.primary_color}
                    onChange={(e) => updateDeployment({ primary_color: e.target.value })}
                    className="h-7 w-8 rounded border border-surface-container-highest"
                  />
                  <span className="font-mono text-sm font-bold">
                    {deployment.primary_color.toUpperCase()}
                  </span>
                </div>
              </label>
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-bold uppercase tracking-widest text-on-surface-variant">
                  Allowed domains
                </span>
                <button
                  type="button"
                  onClick={() => {
                    setIsAddingDomain(true);
                    setDomainDraft('');
                  }}
                  className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-surface-container-highest bg-surface text-brand-primary transition-colors hover:bg-surface-container-low hover:border-brand-primary/30"
                  aria-label="Add domain"
                >
                  <Plus className="h-4 w-4" />
                </button>
              </div>

              {domains.length > 0 ? (
                <ul className="flex flex-wrap gap-2">
                  {domains.map((domain) => (
                    <li
                      key={domain}
                      className="inline-flex items-center gap-1.5 rounded-full border border-surface-container-highest bg-surface-container-low py-1 pl-3 pr-1.5 text-sm font-medium text-brand-primary"
                    >
                      <Globe className="h-3.5 w-3.5 text-on-surface-variant" />
                      {domain}
                      <button
                        type="button"
                        onClick={() => removeDomain(domain)}
                        className="grid h-6 w-6 place-items-center rounded-full text-on-surface-variant transition-colors hover:bg-rose-50 hover:text-rose-600"
                        aria-label={`Remove ${domain}`}
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="rounded-lg border border-dashed border-surface-container-highest bg-surface-container-low px-3 py-4 text-center text-xs text-on-surface-variant">
                  No domains yet. Click + to add one.
                </p>
              )}

              {isAddingDomain && (
                <div className="flex gap-2">
                  <input
                    value={domainDraft}
                    onChange={(e) => setDomainDraft(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        addDomain();
                      }
                      if (e.key === 'Escape') {
                        setIsAddingDomain(false);
                        setDomainDraft('');
                      }
                    }}
                    placeholder="example.com"
                    autoFocus
                    className="h-10 min-w-0 flex-1 rounded-lg border border-surface-container-highest bg-surface-container-low px-3 text-sm focus:border-brand-primary focus:outline-none focus:ring-1 focus:ring-brand-primary/20"
                  />
                  <button
                    type="button"
                    onClick={addDomain}
                    className="h-10 rounded-lg bg-brand-primary px-4 text-xs font-bold text-brand-on-primary hover:opacity-90"
                  >
                    Add
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setIsAddingDomain(false);
                      setDomainDraft('');
                    }}
                    className="grid h-10 w-10 place-items-center rounded-lg border border-surface-container-highest text-on-surface-variant hover:text-brand-primary"
                    aria-label="Cancel"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              )}

              <p className="flex items-center gap-2 text-xs text-on-surface-variant">
                <Shield className="h-3.5 w-3.5 shrink-0" />
                Subdomains of an allowed domain are accepted automatically.
              </p>
            </div>

            <div className="space-y-3 border-t border-surface-container-highest pt-6">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <Code2 className="h-4 w-4 text-on-surface-variant" />
                  <span className="text-xs font-bold uppercase tracking-widest text-on-surface-variant">
                    Embed code
                  </span>
                  <Link
                    to="/guides"
                    className="grid h-8 w-8 place-items-center rounded-lg border border-surface-container-highest bg-surface text-on-surface-variant transition-colors hover:border-brand-primary/30 hover:bg-surface-container-low hover:text-brand-primary"
                    title="Embedding guide"
                    aria-label="Open embedding guide"
                  >
                    <BookOpen className="h-4 w-4" />
                  </Link>
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={regenerateDeploymentId}
                    disabled={isSaving}
                    className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-surface-container-highest px-2.5 text-xs font-bold text-brand-primary disabled:opacity-50"
                  >
                    <RefreshCw className="h-3.5 w-3.5" />
                    Regenerate
                  </button>
                  <button
                    type="button"
                    onClick={copyEmbed}
                    className="inline-flex h-8 items-center gap-1.5 rounded-lg bg-brand-primary px-2.5 text-xs font-bold text-brand-on-primary"
                  >
                    <Copy className="h-3.5 w-3.5" />
                    {copied ? 'Copied' : 'Copy'}
                  </button>
                </div>
              </div>
              <pre className="overflow-x-auto rounded-lg border border-surface-container-highest bg-zinc-950 p-4 text-xs leading-relaxed text-zinc-100">
                <code>{embedCode}</code>
              </pre>
            </div>
          </div>

          <div className="bg-[radial-gradient(#d9d9db_1.5px,transparent_1.5px)] [background-size:28px_28px] p-6 md:p-10">
            <div className="mx-auto max-w-[560px]">
              <WidgetLivePreview
                displayName={displayName}
                logoUrl={deployment.logo_url || agent?.avatar_url}
                theme={deployment.theme}
                primaryColor={deployment.primary_color}
                messages={previewMessages}
                fallbackGreeting={previewGreeting}
              />
            </div>
          </div>
        </div>
    </section>
  );
}
