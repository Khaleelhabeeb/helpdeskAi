import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  ArrowUp,
  BookOpen,
  Camera,
  Check,
  ChevronLeft,
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
  Smartphone,
  X,
} from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
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

const comingSoonChannels = [
  {
    title: 'Email',
    copy: 'Connect your agent to an email address and let it respond to messages from your customers.',
    icon: Mail,
    iconBg: 'bg-[#EA4335]',
  },
  {
    title: 'WhatsApp',
    copy: 'Reply to WhatsApp conversations with the same trained support agent.',
    icon: Smartphone,
    iconBg: 'bg-[#25D366]',
  },
  {
    title: 'Phone',
    copy: 'Let your AI agent handle inbound phone calls.',
    icon: Phone,
    iconBg: 'bg-[#7C3AED]',
    badge: 'Beta',
  },
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

function AgentAvatar({
  name,
  image,
  className,
}: {
  name: string;
  image?: string | null;
  className?: string;
}) {
  if (image) {
    return <img src={image} alt="" className={cn('h-full w-full object-cover', className)} />;
  }
  return (
    <span className={cn('text-xs font-black', className)}>
      {name.slice(0, 2).toUpperCase() || 'AI'}
    </span>
  );
}

function Toggle({
  checked,
  onChange,
  disabled,
}: {
  checked: boolean;
  onChange?: (value: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange?.(!checked)}
      className={cn(
        'relative h-6 w-11 shrink-0 rounded-full transition-colors duration-200',
        checked ? 'bg-emerald-500' : 'bg-zinc-300',
        disabled && 'cursor-not-allowed opacity-60'
      )}
    >
      <span
        className={cn(
          'absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform duration-200',
          checked && 'translate-x-5'
        )}
      />
    </button>
  );
}

function ChatWidgetMiniPreview({
  name,
  logoUrl,
  greeting,
  theme,
  primaryColor,
}: {
  name: string;
  logoUrl?: string | null;
  greeting: string;
  theme: 'light' | 'dark';
  primaryColor: string;
}) {
  const dark = theme === 'dark';
  const sendColor = primaryColor.toLowerCase() === '#ffffff' ? '#111' : '#fff';

  return (
    <div className="pointer-events-none absolute bottom-6 left-1/2 w-[88%] max-w-[220px] -translate-x-1/2">
      <div
        className={cn(
          'overflow-hidden rounded-2xl shadow-2xl ring-1 ring-black/10',
          dark ? 'bg-zinc-950 text-white' : 'bg-white text-zinc-900'
        )}
      >
        <div
          className={cn(
            'flex items-center gap-2 border-b px-3 py-2.5',
            dark ? 'border-zinc-800 bg-zinc-900' : 'border-zinc-200 bg-zinc-50'
          )}
        >
          <div className="grid h-7 w-7 shrink-0 place-items-center overflow-hidden rounded-full bg-white text-black">
            <AgentAvatar name={name} image={logoUrl} />
          </div>
          <span className="truncate text-xs font-bold">{name}</span>
        </div>
        <div className="space-y-2 p-3">
          <div
            className={cn(
              'max-w-[90%] rounded-xl px-3 py-2 text-[11px] leading-snug',
              dark ? 'bg-zinc-900' : 'bg-zinc-100'
            )}
          >
            {greeting}
          </div>
          <div
            className="ml-auto w-fit max-w-[75%] rounded-full px-3 py-1.5 text-[10px] font-medium"
            style={{ backgroundColor: primaryColor, color: sendColor }}
          >
            I need help
          </div>
        </div>
        <div
          className={cn(
            'mx-3 mb-3 flex h-8 items-center rounded-full border px-3',
            dark ? 'border-zinc-700' : 'border-zinc-200'
          )}
        >
          <span className={cn('text-[10px]', dark ? 'text-zinc-500' : 'text-zinc-400')}>Message...</span>
        </div>
      </div>
    </div>
  );
}

function HelpPageMiniPreview({ name }: { name: string }) {
  return (
    <div className="pointer-events-none absolute bottom-5 left-1/2 w-[92%] max-w-[280px] -translate-x-1/2">
      <div className="overflow-hidden rounded-xl bg-zinc-950 shadow-2xl ring-1 ring-black/15">
        <div className="flex items-center gap-1.5 border-b border-zinc-800 bg-zinc-900 px-3 py-2">
          <span className="h-2 w-2 rounded-full bg-red-500/80" />
          <span className="h-2 w-2 rounded-full bg-amber-400/80" />
          <span className="h-2 w-2 rounded-full bg-emerald-500/80" />
          <div className="ml-2 flex items-center gap-1.5">
            <span className="grid h-5 w-5 place-items-center rounded bg-white text-[8px] font-black text-black">
              {name.slice(0, 2).toUpperCase()}
            </span>
            <span className="text-[10px] font-bold text-zinc-300">{name}</span>
          </div>
        </div>
        <div className="px-4 py-6 text-center">
          <h3 className="text-sm font-bold text-white">Hey, I&apos;m {name}</h3>
          <p className="mt-4 rounded-xl border border-zinc-700 bg-zinc-900 px-3 py-2.5 text-left text-[10px] text-zinc-500">
            Ask me anything...
          </p>
          <div className="mt-3 flex justify-end">
            <span className="grid h-7 w-7 place-items-center rounded-lg bg-white text-black">
              <ArrowUp className="h-3.5 w-3.5" />
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

type ChannelCardProps = {
  title: string;
  description: string;
  previewGradient: string;
  preview: React.ReactNode;
  enabled: boolean;
  onToggle?: (enabled: boolean) => void;
  toggleDisabled?: boolean;
  onManage?: () => void;
  manageLabel?: string;
  manageDisabled?: boolean;
  showMobileButton?: boolean;
};

function ChannelCard({
  title,
  description,
  previewGradient,
  preview,
  enabled,
  onToggle,
  toggleDisabled,
  onManage,
  manageLabel = 'Manage',
  manageDisabled,
  showMobileButton,
}: ChannelCardProps) {
  return (
    <article className="flex flex-col overflow-hidden rounded-2xl border border-surface-container-highest bg-surface-container-lowest shadow-sm transition-shadow hover:shadow-md">
      <div
        className={cn(
          'relative h-44 shrink-0 overflow-hidden sm:h-52',
          previewGradient
        )}
      >
        {preview}
      </div>
      <div className="flex flex-1 flex-col p-5 sm:p-6">
        <div className="flex items-start justify-between gap-4">
          <h2 className="text-lg font-bold text-brand-primary sm:text-xl">{title}</h2>
          <Toggle checked={enabled} onChange={onToggle} disabled={toggleDisabled} />
        </div>
        <p className="mt-2 flex-1 text-sm leading-relaxed text-on-surface-variant">{description}</p>
        <div className="mt-5 flex items-center gap-2">
          {showMobileButton && (
            <button
              type="button"
              disabled
              className="grid h-10 w-10 shrink-0 place-items-center rounded-lg border border-surface-container-highest bg-surface text-on-surface-variant/50"
              aria-label="Mobile preview"
            >
              <Smartphone className="h-4 w-4" />
            </button>
          )}
          <button
            type="button"
            onClick={onManage}
            disabled={manageDisabled}
            className={cn(
              'h-10 flex-1 rounded-lg border border-surface-container-highest bg-surface px-4 text-sm font-bold transition-colors',
              manageDisabled
                ? 'cursor-default text-on-surface-variant/50'
                : 'text-brand-primary hover:bg-surface-container-low hover:border-brand-primary/20'
            )}
          >
            {manageLabel}
          </button>
        </div>
      </div>
    </article>
  );
}

function ComingSoonCard({
  title,
  copy,
  icon: Icon,
  iconBg,
  badge,
}: {
  title: string;
  copy: string;
  icon: typeof Mail;
  iconBg: string;
  badge?: string;
}) {
  return (
    <article className="flex flex-col rounded-2xl border border-surface-container-highest bg-surface-container-lowest p-6 shadow-sm sm:p-8">
      <div className={cn('grid h-14 w-14 place-items-center rounded-2xl text-white shadow-sm', iconBg)}>
        <Icon className="h-7 w-7" />
      </div>
      <div className="mt-8 flex items-center gap-2">
        <h2 className="text-xl font-bold text-brand-primary">{title}</h2>
        {badge && (
          <span className="rounded-full bg-brand-primary px-2.5 py-0.5 text-[10px] font-black uppercase tracking-wide text-brand-on-primary">
            {badge}
          </span>
        )}
      </div>
      <p className="mt-3 min-h-[4.5rem] flex-1 text-sm leading-relaxed text-on-surface-variant">{copy}</p>
      <div className="mt-6 flex items-center gap-2">
        <button
          type="button"
          disabled
          className="grid h-10 w-10 shrink-0 place-items-center rounded-lg border border-surface-container-highest bg-surface text-on-surface-variant/40"
          aria-hidden
        >
          <Smartphone className="h-4 w-4" />
        </button>
        <button
          type="button"
          disabled
          className="h-10 flex-1 cursor-not-allowed rounded-lg border border-surface-container-highest bg-surface-container-low px-4 text-sm font-bold text-on-surface-variant/60"
        >
          Coming soon
        </button>
      </div>
    </article>
  );
}

export default function AgentDeploy() {
  const { agentId } = useParams();
  const navigate = useNavigate();
  const [agent, setAgent] = useState<Agent | null>(null);
  const [deployment, setDeployment] = useState<WidgetDeployment>(() => defaultDeployment());
  const [savedDeployment, setSavedDeployment] = useState<WidgetDeployment | null>(null);
  const [domains, setDomains] = useState<string[]>(['localhost', '127.0.0.1']);
  const [savedDomains, setSavedDomains] = useState<string[]>(['localhost', '127.0.0.1']);
  const [domainDraft, setDomainDraft] = useState('');
  const [isAddingDomain, setIsAddingDomain] = useState(false);
  const [isLoading, setLoading] = useState(true);
  const [isSaving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [copied, setCopied] = useState(false);
  const [isUploadingLogo, setUploadingLogo] = useState(false);
  const [widgetPanelOpen, setWidgetPanelOpen] = useState(false);
  const [helpPageEnabled, setHelpPageEnabled] = useState(false);

  const isDirty = useMemo(() => {
    if (!savedDeployment) return false;
    return (
      JSON.stringify(deployment) !== JSON.stringify(savedDeployment) ||
      JSON.stringify(domains) !== JSON.stringify(savedDomains)
    );
  }, [deployment, domains, savedDeployment, savedDomains]);

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
        const loadedDomains = data.allowed_domains?.length
          ? data.allowed_domains
          : ['localhost', '127.0.0.1'];
        setDomains(loadedDomains);
        setSavedDomains(loadedDomains);
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

  const previewGreeting =
    deployment.initial_messages.find((m) => m.trim())?.trim() ?? 'Hi! What can I help you with?';
  const displayName = deployment.display_name || agent?.name || 'Support Agent';
  const dark = deployment.theme === 'dark';
  const sendTextColor =
    deployment.primary_color.toLowerCase() === '#ffffff' ? '#111111' : '#ffffff';
  const previewMessages = deployment.initial_messages.filter((m) => m.trim());

  function updateDeployment(patch: Partial<WidgetDeployment>) {
    setDeployment((current) => ({ ...current, ...patch }));
    setNotice('');
  }

  function updateInitialMessage(index: number, value: string) {
    updateDeployment({
      initial_messages: deployment.initial_messages.map((message, idx) =>
        idx === index ? value : message
      ),
    });
  }

  function removeInitialMessage(index: number) {
    const next = deployment.initial_messages.filter((_, idx) => idx !== index);
    updateDeployment({ initial_messages: next.length ? next : [''] });
  }

  function addInitialMessage() {
    updateDeployment({ initial_messages: [...deployment.initial_messages, ''] });
  }

  function normalizeDomain(value: string) {
    return value
      .trim()
      .toLowerCase()
      .replace(/^https?:\/\//, '')
      .replace(/\/.*$/, '')
      .replace(/^www\./, '');
  }

  function addDomain() {
    const normalized = normalizeDomain(domainDraft);
    if (!normalized) return;
    if (!domains.includes(normalized)) {
      setDomains((current) => [...current, normalized]);
      setNotice('');
    }
    setDomainDraft('');
    setIsAddingDomain(false);
  }

  function removeDomain(domain: string) {
    setDomains((current) => current.filter((item) => item !== domain));
    setNotice('');
  }

  const logoImage = deployment.logo_url || agent?.avatar_url || null;

  async function saveDeployment() {
    if (!agent) return;
    setSaving(true);
    setError('');
    setNotice('');
    try {
      const updated = await apiFetch<WidgetDeployment>(`/agents/${agent.id}/widget-deployment`, {
        method: 'PATCH',
        body: JSON.stringify({
          display_name: deployment.display_name,
          logo_url: deployment.logo_url,
          initial_messages: deployment.initial_messages,
          theme: deployment.theme,
          primary_color: deployment.primary_color,
          allowed_domains: domains,
          is_enabled: deployment.is_enabled,
        }),
      });
      setDeployment(updated);
      setSavedDeployment(updated);
      const nextDomains = updated.allowed_domains?.length
        ? updated.allowed_domains
        : domains;
      setDomains(nextDomains);
      setSavedDomains(nextDomains);
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
      const updated = await apiFetch<WidgetDeployment>(
        `/agents/${agent.id}/widget-deployment/regenerate`,
        { method: 'POST' }
      );
      setDeployment(updated);
      setSavedDeployment(updated);
      const nextDomains = updated.allowed_domains?.length
        ? updated.allowed_domains
        : domains;
      setDomains(nextDomains);
      setSavedDomains(nextDomains);
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

  return (
    <AppLayout>
      <div className="space-y-8">
        <header>
          <button
            type="button"
            onClick={() => (widgetPanelOpen ? setWidgetPanelOpen(false) : navigate('/agents'))}
            className="mb-4 inline-flex items-center gap-2 text-sm font-bold text-on-surface-variant transition-colors hover:text-brand-primary"
          >
            {widgetPanelOpen ? (
              <>
                <ChevronLeft className="h-4 w-4" />
                Back to channels
              </>
            ) : (
              <>
                <ArrowLeft className="h-4 w-4" />
                Back to agent
              </>
            )}
          </button>
          <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h1 className="text-3xl font-bold tracking-tight text-brand-primary sm:text-4xl">
                {widgetPanelOpen ? 'Chat widget' : 'Deploy'}
              </h1>
              <p className="mt-2 text-sm text-on-surface-variant">
                {widgetPanelOpen
                  ? `Customize how ${agent?.name ?? 'your agent'} appears on your website.`
                  : `Choose where ${agent?.name ?? 'your agent'} shows up for customers.`}
              </p>
            </div>
            {widgetPanelOpen && (
              <div className="flex items-center gap-3">
                {isDirty && (
                  <span className="text-xs font-bold uppercase tracking-widest text-amber-600">
                    Unsaved changes
                  </span>
                )}
                <button
                  type="button"
                  onClick={saveDeployment}
                  disabled={isSaving || !isDirty}
                  className="inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-brand-primary px-5 text-sm font-bold text-brand-on-primary disabled:opacity-50"
                >
                  {isSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                  Save widget
                </button>
              </div>
            )}
          </div>
        </header>

        {(error || notice) && (
          <div
            className={cn(
              'rounded-lg border px-4 py-3 text-sm font-medium',
              error
                ? 'border-rose-200 bg-rose-50 text-rose-700'
                : 'border-emerald-200 bg-emerald-50 text-emerald-700'
            )}
          >
            {error || notice}
          </div>
        )}

        {isLoading ? (
          <div className="flex min-h-[360px] items-center justify-center rounded-2xl border border-surface-container-highest bg-surface-container-lowest text-sm font-medium text-on-surface-variant">
            <Loader2 className="mr-2 h-5 w-5 animate-spin" />
            Loading channels...
          </div>
        ) : (
          <>
            <AnimatePresence mode="wait">
              {!widgetPanelOpen ? (
                <motion.div
                  key="channels-grid"
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ duration: 0.25 }}
                  className="space-y-6"
                >
                  <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                    <ChannelCard
                      title="Chat widget"
                      description="Add a floating chat window to your site."
                      previewGradient="bg-gradient-to-br from-sky-100 via-sky-50 to-indigo-100"
                      preview={
                        <ChatWidgetMiniPreview
                          name={displayName}
                          logoUrl={deployment.logo_url || agent?.avatar_url}
                          greeting={previewGreeting}
                          theme={deployment.theme}
                          primaryColor={deployment.primary_color}
                        />
                      }
                      enabled={deployment.is_enabled}
                      onToggle={(value) => updateDeployment({ is_enabled: value })}
                      onManage={() => setWidgetPanelOpen(true)}
                      showMobileButton
                    />

                    <ChannelCard
                      title="Help page"
                      description="ChatGPT-style help page, deployed standalone or under a path on your site (/help)."
                      previewGradient="bg-gradient-to-br from-amber-100 via-orange-50 to-yellow-100"
                      preview={<HelpPageMiniPreview name={displayName} />}
                      enabled={helpPageEnabled}
                      onToggle={setHelpPageEnabled}
                      toggleDisabled
                      onManage={() => undefined}
                      manageLabel="Manage"
                      manageDisabled
                    />
                  </div>

                  <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
                    {comingSoonChannels.map((channel) => (
                      <ComingSoonCard key={channel.title} {...channel} />
                    ))}
                  </div>
                </motion.div>
              ) : (
                <motion.section
                  key="widget-config"
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ duration: 0.28 }}
                  className="overflow-hidden rounded-2xl border border-surface-container-highest bg-surface-container-lowest shadow-sm"
                >
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
                          <span className="text-xs font-bold uppercase tracking-widest text-on-surface-variant">
                            Style
                          </span>
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
                      <div className="mx-auto flex max-w-[560px] flex-col items-center">
                        <div
                          className={cn(
                            'h-[520px] w-full overflow-hidden rounded-[28px] shadow-2xl',
                            dark ? 'bg-black text-white' : 'bg-white text-black'
                          )}
                        >
                          <div
                            className={cn(
                              'flex h-16 items-center gap-3 px-5',
                              dark ? 'bg-zinc-900' : 'bg-zinc-100'
                            )}
                          >
                            <div className="grid h-10 w-10 place-items-center overflow-hidden rounded-full bg-white text-black">
                              <AgentAvatar
                                name={displayName}
                                image={deployment.logo_url || agent?.avatar_url}
                              />
                            </div>
                            <div className="font-bold">{displayName}</div>
                            <Check className="ml-auto h-5 w-5 text-emerald-500" />
                          </div>
                          <div className="flex h-[calc(100%-4rem)] flex-col p-5">
                            <div className="flex-1 space-y-3 overflow-y-auto">
                              {(previewMessages.length ? previewMessages : [previewGreeting]).map(
                                (message, index) => (
                                  <div
                                    key={`${message}-${index}`}
                                    className={cn(
                                      'max-w-[78%] rounded-2xl px-4 py-3 text-sm',
                                      dark ? 'bg-zinc-900 text-zinc-100' : 'bg-zinc-100 text-zinc-900'
                                    )}
                                  >
                                    {message}
                                  </div>
                                )
                              )}
                              <div
                                className="ml-auto w-fit rounded-2xl px-4 py-2.5 text-sm"
                                style={{
                                  backgroundColor: deployment.primary_color,
                                  color: sendTextColor,
                                }}
                              >
                                Thanks, I need help.
                              </div>
                            </div>
                            <div
                              className={cn(
                                'mt-4 flex h-12 items-center gap-3 rounded-full border px-4',
                                dark ? 'border-zinc-700' : 'border-zinc-200'
                              )}
                            >
                              <span
                                className={cn(
                                  'flex-1 text-sm',
                                  dark ? 'text-zinc-500' : 'text-zinc-400'
                                )}
                              >
                                Message...
                              </span>
                              <span
                                className="grid h-9 w-9 place-items-center rounded-full"
                                style={{
                                  backgroundColor: deployment.primary_color,
                                  color: sendTextColor,
                                }}
                              >
                                <ArrowUp className="h-4 w-4" />
                              </span>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </motion.section>
              )}
            </AnimatePresence>
          </>
        )}
      </div>
    </AppLayout>
  );
}
