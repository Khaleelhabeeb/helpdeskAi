import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  Check,
  Code2,
  Copy,
  Globe,
  Loader2,
  Mail,
  MessageCircle,
  Phone,
  Plus,
  RefreshCw,
  Save,
  Shield,
  ShoppingBag,
  Smartphone,
  X,
} from 'lucide-react';
import { AppLayout } from '../components/Layout';
import { Agent, apiFetch, API_BASE_URL } from '../lib/api';
import { cn } from '../lib/utils';

type WidgetDeployment = {
  deployment_id: string;
  display_name: string;
  logo_url: string;
  initial_messages: string[];
  theme: 'light' | 'dark';
  primary_color: string;
  allowed_domains: string[];
  is_enabled: boolean;
  embed_script: string;
};

const secondaryChannels = [
  { title: 'Email', copy: 'Connect your agent to an email address and let it respond to customer messages.', icon: Mail, color: 'bg-red-500 text-white', action: 'Setup' },
  { title: 'Shopify', copy: 'Connect your agent to Shopify and help customers with order and product questions.', icon: ShoppingBag, color: 'bg-lime-500 text-white', action: 'Setup' },
  { title: 'Phone', copy: 'Let your AI agent handle inbound phone calls.', icon: Phone, color: 'bg-violet-600 text-white', action: 'Setup', badge: 'Beta' },
  { title: 'WhatsApp', copy: 'Reply to WhatsApp conversations with the same trained support agent.', icon: Smartphone, color: 'bg-emerald-500 text-white', action: 'Setup' },
];

function defaultDeployment(agent?: Agent | null): WidgetDeployment {
  const displayName = agent?.name || 'Support Agent';
  return {
    deployment_id: '',
    display_name: displayName,
    logo_url: agent?.avatar_url || '',
    initial_messages: ['Hi! What can I help you with?'],
    theme: 'dark',
    primary_color: '#ffffff',
    allowed_domains: ['localhost', '127.0.0.1'],
    is_enabled: true,
    embed_script: `<script src="${API_BASE_URL}/static/widget.js" data-deployment-id="" defer></script>`,
  };
}

function AgentInitials({ name }: { name: string }) {
  return <span className="text-xs font-black">{name.slice(0, 2).toUpperCase() || 'AI'}</span>;
}

export default function AgentDeploy() {
  const { agentId } = useParams();
  const navigate = useNavigate();
  const [agent, setAgent] = useState<Agent | null>(null);
  const [deployment, setDeployment] = useState<WidgetDeployment>(() => defaultDeployment());
  const [savedDeployment, setSavedDeployment] = useState<WidgetDeployment | null>(null);
  const [domainText, setDomainText] = useState('localhost\n127.0.0.1');
  const [savedDomainText, setSavedDomainText] = useState('localhost\n127.0.0.1');
  const [isLoading, setLoading] = useState(true);
  const [isSaving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [copied, setCopied] = useState(false);
  const [isUploadingLogo, setUploadingLogo] = useState(false);

  const isDirty = useMemo(() => {
    if (!savedDeployment) return false;
    return JSON.stringify(deployment) !== JSON.stringify(savedDeployment) || domainText !== savedDomainText;
  }, [deployment, domainText, savedDeployment, savedDomainText]);

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError('');
      try {
        const agents = await apiFetch<Agent[]>('/agents/');
        const found = agents.find((item) => item.id === agentId) ?? null;
        if (!found) throw new Error('Agent not found');
        setAgent(found);
        const data = await apiFetch<WidgetDeployment>(`/agents/${found.id}/widget-deployment`);
        setDeployment(data);
        setSavedDeployment(data);
        setDomainText((data.allowed_domains || []).join('\n'));
        setSavedDomainText((data.allowed_domains || []).join('\n'));
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Could not load deploy page');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [agentId]);

  const embedCode = useMemo(() => {
    if (deployment.embed_script) return deployment.embed_script;
    return `<script src="${API_BASE_URL}/static/widget.js" data-deployment-id="${deployment.deployment_id}" defer></script>`;
  }, [deployment.embed_script, deployment.deployment_id]);

  function updateDeployment(patch: Partial<WidgetDeployment>) {
    setDeployment((current) => ({ ...current, ...patch }));
    setNotice('');
  }

  function updateInitialMessage(index: number, value: string) {
    updateDeployment({
      initial_messages: deployment.initial_messages.map((message, idx) => (idx === index ? value : message)),
    });
  }

  function removeInitialMessage(index: number) {
    const next = deployment.initial_messages.filter((_, idx) => idx !== index);
    updateDeployment({ initial_messages: next.length ? next : [''] });
  }

  function addInitialMessage() {
    updateDeployment({ initial_messages: [...deployment.initial_messages, ''] });
  }

  async function saveDeployment() {
    if (!agent) return;
    setSaving(true);
    setError('');
    setNotice('');
    try {
      const allowed_domains = domainText
        .split(/[\n,]/)
        .map((domain) => domain.trim())
        .filter(Boolean);
      const updated = await apiFetch<WidgetDeployment>(`/agents/${agent.id}/widget-deployment`, {
        method: 'PATCH',
        body: JSON.stringify({
          display_name: deployment.display_name,
          logo_url: deployment.logo_url,
          initial_messages: deployment.initial_messages,
          theme: deployment.theme,
          primary_color: deployment.primary_color,
          allowed_domains,
          is_enabled: deployment.is_enabled,
        }),
      });
      setDeployment(updated);
      setSavedDeployment(updated);
      setDomainText((updated.allowed_domains || []).join('\n'));
      setSavedDomainText((updated.allowed_domains || []).join('\n'));
      setNotice('Widget deployment saved.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save widget deployment');
    } finally {
      setSaving(false);
    }
  }

  async function regenerateDeploymentId() {
    if (!agent) return;
    setSaving(true);
    setError('');
    setNotice('');
    try {
      const updated = await apiFetch<WidgetDeployment>(`/agents/${agent.id}/widget-deployment/regenerate`, { method: 'POST' });
      setDeployment(updated);
      setSavedDeployment(updated);
      setDomainText((updated.allowed_domains || []).join('\n'));
      setSavedDomainText((updated.allowed_domains || []).join('\n'));
      setNotice('Embed key regenerated. Replace the old snippet on any websites using this widget.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not regenerate deployment key');
    } finally {
      setSaving(false);
    }
  }

  async function copyEmbed() {
    await navigator.clipboard?.writeText(embedCode);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1400);
  }

  async function uploadLogo(file: File) {
    if (!agent) return;
    setUploadingLogo(true);
    setError('');
    setNotice('');
    try {
      const body = new FormData();
      body.append('avatar', file);
      const updated = await apiFetch<Agent>(`/agents/${agent.id}/avatar`, { method: 'POST', body });
      setAgent(updated);
      updateDeployment({ logo_url: updated.avatar_url || '' });
      setNotice('Logo uploaded. Remember to save the widget settings.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not upload logo');
    } finally {
      setUploadingLogo(false);
    }
  }

  const nonEmptyInitialMessages = deployment.initial_messages.filter((message) => message.trim());
  const previewMessages = nonEmptyInitialMessages.length ? nonEmptyInitialMessages : ['Hi! What can I help you with?'];
  const dark = deployment.theme === 'dark';
  const sendTextColor = deployment.primary_color.toLowerCase() === '#ffffff' ? '#111111' : '#ffffff';

  return (
    <AppLayout>
      <div className="space-y-8">
        <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <button onClick={() => navigate('/agents')} className="mb-6 inline-flex items-center gap-2 text-sm font-bold text-on-surface-variant hover:text-brand-primary">
              <ArrowLeft className="h-4 w-4" />
              Back to playground
            </button>
            <h1 className="text-4xl font-bold tracking-tight text-brand-primary">All channels</h1>
            <p className="mt-2 text-sm font-medium text-on-surface-variant">Deploy {agent?.name ?? 'your agent'} wherever customers already are.</p>
          </div>
          <div className="flex items-center gap-3">
            {isDirty && <span className="text-xs font-black uppercase tracking-widest text-amber-600">Unsaved changes</span>}
            <button onClick={saveDeployment} disabled={isSaving || !isDirty} className="inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-brand-primary px-5 text-sm font-bold text-brand-on-primary disabled:opacity-50">
              {isSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              Save widget
            </button>
          </div>
        </header>

        {(error || notice) && <div className={cn('rounded-lg border px-4 py-3 text-sm font-medium', error ? 'border-rose-200 bg-rose-50 text-rose-700' : 'border-emerald-200 bg-emerald-50 text-emerald-700')}>{error || notice}</div>}

        {isLoading ? (
          <div className="min-h-[320px] rounded-xl border border-surface-container-highest bg-surface-container-lowest p-10 text-sm font-bold text-on-surface-variant">Loading channels...</div>
        ) : (
          <>
            <section className="overflow-hidden rounded-xl border border-surface-container-highest bg-surface-container-lowest shadow-sm">
              <div className="grid grid-cols-1 xl:grid-cols-[480px_1fr]">
                <div className="space-y-7 border-b border-surface-container-highest p-6 xl:border-b-0 xl:border-r">
                  <div>
                    <div className="flex items-center gap-3">
                      <div className="grid h-12 w-12 place-items-center rounded-xl bg-blue-500 text-white"><MessageCircle className="h-6 w-6" /></div>
                      <div>
                        <h2 className="text-2xl font-bold text-brand-primary">Chat widget</h2>
                        <p className="text-sm font-medium text-on-surface-variant">Customize the embed before copying it.</p>
                      </div>
                    </div>
                  </div>

                  <label className="block space-y-2">
                    <span className="text-xs font-black uppercase tracking-widest text-on-surface-variant">Display name</span>
                    <input value={deployment.display_name} onChange={(event) => updateDeployment({ display_name: event.target.value })} className="h-11 w-full rounded-lg border border-surface-container-highest bg-surface-container-low px-4 text-sm focus:border-brand-primary focus:outline-none" />
                  </label>

                  <label className="block space-y-2">
                    <span className="text-xs font-black uppercase tracking-widest text-on-surface-variant">Display logo</span>
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                      <label className="flex h-11 w-full cursor-pointer items-center justify-center gap-2 rounded-lg border border-dashed border-surface-container-highest bg-surface-container-low text-xs font-bold text-brand-primary hover:border-brand-primary">
                        <input
                          type="file"
                          accept="image/png,image/jpeg,image/webp,image/svg+xml"
                          className="hidden"
                          onChange={(event) => {
                            const file = event.target.files?.[0];
                            if (file) uploadLogo(file);
                          }}
                        />
                        {isUploadingLogo ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                        {isUploadingLogo ? 'Uploading...' : 'Upload logo'}
                      </label>
                      <input
                        value={deployment.logo_url}
                        onChange={(event) => updateDeployment({ logo_url: event.target.value })}
                        placeholder="https://example.com/logo.png"
                        className="h-11 w-full rounded-lg border border-surface-container-highest bg-surface-container-low px-4 text-sm focus:border-brand-primary focus:outline-none"
                      />
                    </div>
                    <span className="text-xs font-medium text-on-surface-variant">Upload a square PNG, JPG, WEBP, or SVG. This appears as the chat avatar.</span>
                  </label>

                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-black uppercase tracking-widest text-on-surface-variant">Initial messages</span>
                      <button onClick={addInitialMessage} className="inline-flex items-center gap-1 text-xs font-bold text-brand-primary"><Plus className="h-3.5 w-3.5" />Add</button>
                    </div>
                    {deployment.initial_messages.map((message, index) => (
                      <div key={index} className="flex gap-2">
                        <input value={message} onChange={(event) => updateInitialMessage(index, event.target.value)} className="h-11 min-w-0 flex-1 rounded-lg border border-surface-container-highest bg-surface-container-low px-4 text-sm focus:border-brand-primary focus:outline-none" />
                        <button onClick={() => removeInitialMessage(index)} className="grid h-11 w-11 place-items-center rounded-lg border border-surface-container-highest bg-surface-container-low text-on-surface-variant hover:text-rose-600" aria-label="Remove message"><X className="h-4 w-4" /></button>
                      </div>
                    ))}
                  </div>

                  <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
                    <div className="space-y-2">
                      <span className="text-xs font-black uppercase tracking-widest text-on-surface-variant">Style</span>
                      <div className="grid grid-cols-2 rounded-lg border border-surface-container-highest bg-surface-container-low p-1">
                        {(['dark', 'light'] as const).map((theme) => (
                          <button key={theme} onClick={() => updateDeployment({ theme })} className={cn('h-9 rounded-md text-sm font-bold capitalize', deployment.theme === theme ? 'bg-brand-primary text-brand-on-primary' : 'text-on-surface-variant')}>{theme}</button>
                        ))}
                      </div>
                    </div>
                    <label className="space-y-2">
                      <span className="text-xs font-black uppercase tracking-widest text-on-surface-variant">Primary color</span>
                      <div className="flex h-11 items-center gap-3 rounded-lg border border-surface-container-highest bg-surface-container-low px-3">
                        <input type="color" value={deployment.primary_color} onChange={(event) => updateDeployment({ primary_color: event.target.value })} className="h-7 w-8 rounded border border-surface-container-highest" />
                        <span className="font-mono text-sm font-bold">{deployment.primary_color.toUpperCase()}</span>
                      </div>
                    </label>
                  </div>

                  <label className="block space-y-2">
                    <span className="text-xs font-black uppercase tracking-widest text-on-surface-variant">Allowed domains</span>
                    <textarea value={domainText} onChange={(event) => { setDomainText(event.target.value); setNotice(''); }} rows={4} placeholder="example.com&#10;app.example.com" className="w-full resize-none rounded-lg border border-surface-container-highest bg-surface-container-low p-4 text-sm focus:border-brand-primary focus:outline-none" />
                    <span className="flex items-center gap-2 text-xs font-medium text-on-surface-variant"><Shield className="h-3.5 w-3.5" />One domain per line. Subdomains are allowed automatically.</span>
                  </label>

                  <label className="flex items-center justify-between rounded-lg border border-surface-container-highest bg-surface-container-low p-4">
                    <span>
                      <span className="block text-sm font-bold text-brand-primary">Widget enabled</span>
                      <span className="text-xs font-medium text-on-surface-variant">Turn this off to reject public widget traffic.</span>
                    </span>
                    <input type="checkbox" checked={deployment.is_enabled} onChange={(event) => updateDeployment({ is_enabled: event.target.checked })} className="h-5 w-5 accent-brand-primary" />
                  </label>
                </div>

                <div className="bg-[radial-gradient(#d9d9db_1.5px,transparent_1.5px)] [background-size:28px_28px] p-6 md:p-10">
                  <div className="mx-auto flex max-w-[560px] flex-col items-center gap-6">
                    <div className={cn('h-[650px] w-full overflow-hidden rounded-[28px] shadow-2xl', dark ? 'bg-black text-white' : 'bg-white text-black')}>
                      <div className={cn('flex h-20 items-center gap-4 px-6', dark ? 'bg-zinc-900' : 'bg-zinc-100')}>
                        <div className="grid h-11 w-11 place-items-center overflow-hidden rounded-full bg-white text-black">
                          {deployment.logo_url ? <img src={deployment.logo_url} alt="" className="h-full w-full object-cover" /> : <AgentInitials name={deployment.display_name} />}
                        </div>
                        <div className="text-lg font-bold">{deployment.display_name || 'Support Agent'}</div>
                        <Check className="ml-auto h-5 w-5 text-emerald-500" />
                      </div>
                      <div className="flex h-[calc(100%-5rem)] flex-col p-6">
                        <div className="flex-1 space-y-4 overflow-y-auto">
                          {previewMessages.map((message, index) => (
                            <div key={`${message}-${index}`} className={cn('max-w-[78%] rounded-2xl px-4 py-3 text-sm leading-relaxed', dark ? 'bg-zinc-900 text-zinc-100' : 'bg-zinc-100 text-zinc-900')}>{message}</div>
                          ))}
                          <div className="ml-auto w-fit max-w-[76%] rounded-2xl px-4 py-3 text-sm" style={{ backgroundColor: deployment.primary_color, color: sendTextColor }}>Thanks, I need help.</div>
                        </div>
                        <div className={cn('mt-5 flex h-14 items-center gap-3 rounded-full border px-4', dark ? 'border-zinc-700' : 'border-zinc-200')}>
                          <span className={cn('min-w-0 flex-1 text-sm', dark ? 'text-zinc-500' : 'text-zinc-400')}>Message...</span>
                          <button className="grid h-10 w-10 place-items-center rounded-full" style={{ backgroundColor: deployment.primary_color, color: sendTextColor }}><ArrowLeft className="h-4 w-4 rotate-90" /></button>
                        </div>
                      </div>
                    </div>
                    <div className="w-full rounded-xl border border-surface-container-highest bg-surface-container-lowest p-5 shadow-sm">
                      <div className="mb-3 flex items-center justify-between gap-3">
                        <div className="flex items-center gap-2 text-sm font-black uppercase tracking-widest text-on-surface-variant"><Code2 className="h-4 w-4" />Embed code</div>
                        <div className="flex gap-2">
                          <button onClick={regenerateDeploymentId} disabled={isSaving} className="inline-flex h-9 items-center gap-2 rounded-lg border border-surface-container-highest px-3 text-xs font-bold text-brand-primary"><RefreshCw className="h-4 w-4" />Regenerate</button>
                          <button onClick={copyEmbed} className="inline-flex h-9 items-center gap-2 rounded-lg bg-brand-primary px-3 text-xs font-bold text-brand-on-primary"><Copy className="h-4 w-4" />{copied ? 'Copied' : 'Copy'}</button>
                        </div>
                      </div>
                      <pre className="overflow-x-auto rounded-lg bg-black p-4 text-xs text-white"><code>{embedCode}</code></pre>
                    </div>
                  </div>
                </div>
              </div>
            </section>

            <section>
              <div className="mb-5 flex items-center gap-2 text-sm font-black uppercase tracking-widest text-on-surface-variant"><Globe className="h-4 w-4" />More channels</div>
              <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-4">
                {secondaryChannels.map((channel) => (
                  <section key={channel.title} className="rounded-xl border border-surface-container-highest bg-surface-container-lowest p-8 shadow-sm">
                    <div className={cn('grid h-16 w-16 place-items-center rounded-xl shadow-sm', channel.color)}>
                      <channel.icon className="h-8 w-8" />
                    </div>
                    <div className="mt-10 flex items-center gap-3">
                      <h2 className="text-2xl font-bold text-brand-primary">{channel.title}</h2>
                      {channel.badge && <span className="rounded-full bg-black px-3 py-1 text-xs font-black text-white">{channel.badge}</span>}
                    </div>
                    <p className="mt-3 min-h-20 text-base font-medium leading-relaxed text-on-surface-variant">{channel.copy}</p>
                    <button className="mt-8 h-12 w-full rounded-lg border border-surface-container-highest bg-surface-container-low px-5 text-sm font-bold text-brand-primary hover:bg-surface-container">{channel.action}</button>
                  </section>
                ))}
              </div>
            </section>
          </>
        )}
      </div>
    </AppLayout>
  );
}
