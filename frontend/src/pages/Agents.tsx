import {
  ArrowRight,
  Bot,
  Check,
  ChevronDown,
  ChevronLeft,
  Code2,
  Database,
  FileText,
  Handshake,
  Link as LinkIcon,
  Loader2,
  MessageCircle,
  Moon,
  MoreHorizontal,
  Plus,
  RotateCcw,
  Save,
  Settings,
  ShieldCheck,
  Sparkles,
  Sun,
  Trash2,
  Upload,
  RefreshCw,
  Send,
  Users,
  X,
  Zap,
} from 'lucide-react';
import { AppLayout } from '../components/Layout';
import { cn } from '../lib/utils';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { motion } from 'motion/react';
import { Agent, apiFetch, formatRelative, KnowledgeBase } from '../lib/api';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const defaultModel = 'groq/llama-3.1-8b-instant';

type CreateStep = 'source' | 'appearance';
type ManualSource = 'website' | 'file' | 'text' | 'qa';
type KnowledgeSourceMode = 'url' | 'file' | 'text';

type WizardState = {
  name: string;
  website: string;
  useCase: string;
  manual: boolean;
  manualSource: ManualSource;
  manualUrl: string;
  plainText: string;
  qaText: string;
  file: File | null;
  theme: 'light' | 'dark';
  color: string;
  useColorHeader: boolean;
  logoUrl: string | null;
};

type AgentSettingsResponse = {
  widget: {
    theme: 'light' | 'dark' | 'auto';
    color: string;
    position: string;
    greeting: string;
    use_color_header: boolean;
  };
  human_handoff?: {
    enabled: boolean;
    difficulty: 'easy' | 'balanced' | 'hard';
    effective: boolean;
    has_team: boolean;
    active_human_count: number;
  };
};

type ModelOption = {
  id: string;
  label: string;
  provider: string;
  logo?: string;
  locked?: boolean;
};

type AgentTab = 'playground' | 'sources' | 'settings';

type ChatMessage = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  status?: 'streaming';
};

function buildMessageId() {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function formatModelLabel(model?: string) {
  if (!model) return 'Default model';
  const parts = model.split('/');
  return parts[parts.length - 1] || model;
}

function normalizeUrl(input: string): string {
  const trimmed = input.trim();
  if (!trimmed) return '';
  if (/^[a-zA-Z][a-zA-Z\d+\-.]*:\/\//.test(trimmed)) return trimmed;
  if (trimmed.startsWith('//')) return `https:${trimmed}`;
  return `https://${trimmed}`;
}

const markdownComponents = {
  h1: ({ children }: { children: React.ReactNode }) => <h1 className="text-lg font-bold text-zinc-950">{children}</h1>,
  h2: ({ children }: { children: React.ReactNode }) => <h2 className="text-base font-bold text-zinc-950">{children}</h2>,
  h3: ({ children }: { children: React.ReactNode }) => <h3 className="text-sm font-bold text-zinc-950">{children}</h3>,
  p: ({ children }: { children: React.ReactNode }) => <p className="text-sm leading-relaxed text-on-surface-variant">{children}</p>,
  ul: ({ children }: { children: React.ReactNode }) => <ul className="ml-5 list-disc space-y-2 text-sm text-on-surface-variant">{children}</ul>,
  ol: ({ children }: { children: React.ReactNode }) => <ol className="ml-5 list-decimal space-y-2 text-sm text-on-surface-variant">{children}</ol>,
  li: ({ children }: { children: React.ReactNode }) => <li className="leading-relaxed">{children}</li>,
  a: ({ children, href }: { children: React.ReactNode; href?: string }) => (
    <a href={href} className="font-semibold text-zinc-950 underline decoration-brand-primary/40 underline-offset-4" target="_blank" rel="noreferrer">
      {children}
    </a>
  ),
  strong: ({ children }: { children: React.ReactNode }) => <strong className="font-semibold text-zinc-950">{children}</strong>,
  code: ({ children }: { children: React.ReactNode }) => <code className="rounded bg-surface-container-low px-1.5 py-0.5 text-xs font-semibold text-zinc-950">{children}</code>,
  pre: ({ children }: { children: React.ReactNode }) => <pre className="overflow-x-auto rounded-lg bg-surface-container-low p-3 text-xs text-on-surface-variant">{children}</pre>,
  blockquote: ({ children }: { children: React.ReactNode }) => <blockquote className="border-l-2 border-brand-primary/40 pl-3 text-sm text-on-surface-variant">{children}</blockquote>,
  table: ({ children }: { children: React.ReactNode }) => <table className="w-full border-collapse text-left text-xs">{children}</table>,
  thead: ({ children }: { children: React.ReactNode }) => <thead className="bg-surface-container-high text-[11px] uppercase tracking-widest text-on-surface-variant">{children}</thead>,
  tbody: ({ children }: { children: React.ReactNode }) => <tbody className="divide-y divide-surface-container-highest">{children}</tbody>,
  tr: ({ children }: { children: React.ReactNode }) => <tr className="divide-x divide-surface-container-highest">{children}</tr>,
  th: ({ children }: { children: React.ReactNode }) => <th className="px-3 py-2 font-semibold text-on-surface-variant">{children}</th>,
  td: ({ children }: { children: React.ReactNode }) => <td className="px-3 py-2 text-on-surface-variant">{children}</td>,
  hr: () => <hr className="my-3 border-hairline" />,
};

function initialWizard(): WizardState {
  return {
    name: '',
    website: '',
    useCase: 'customer support agent',
    manual: false,
    manualSource: 'website',
    manualUrl: '',
    plainText: '',
    qaText: '',
    file: null,
    theme: 'dark',
    color: '#ffffff',
    useColorHeader: false,
    logoUrl: null,
  };
}

function sourceLabel(sourceType: KnowledgeBase['source_type']) {
  if (sourceType === 'url') return 'URL';
  if (sourceType === 'text') return 'Text';
  if (sourceType === 'upload_pdf') return 'PDF';
  if (sourceType === 'upload_txt') return 'TXT';
  return 'File';
}

function AgentInitials({ name, image }: { name: string; image?: string | null }) {
  if (image) {
    return <img src={image} alt="" className="h-full w-full object-cover" />;
  }
  return <span className="text-sm font-black">{name.slice(0, 2).toUpperCase() || 'AI'}</span>;
}

const GROQ_LOGO_URL = 'https://upload.wikimedia.org/wikipedia/commons/c/cc/Groq_logo.svg';
const OPENAI_LOGO_URL = 'https://i.pinimg.com/1200x/b3/3f/0d/b33f0d10bab5c0d68a006844f7eda264.jpg';
const META_LOGO_URL = 'https://i.pinimg.com/1200x/0a/db/09/0adb09b6580d9c13a6fd4af026649940.jpg';

function resolveModelBadgeSrc(logo?: string, provider?: string, modelId?: string): { src: string; alt: string } {
  const combined = `${logo ?? ''} ${provider ?? ''} ${modelId ?? ''}`.toLowerCase();
  if (combined.includes('openai') || combined.includes('gpt')) return { src: OPENAI_LOGO_URL, alt: 'OpenAI' };
  if (combined.includes('meta') || combined.includes('llama')) return { src: META_LOGO_URL, alt: 'Meta' };
  return { src: GROQ_LOGO_URL, alt: 'Groq' };
}

function ModelLogo({ logo, provider, modelId }: { logo?: string; provider?: string; modelId?: string }) {
  const { src, alt } = resolveModelBadgeSrc(logo, provider, modelId);
  return (
    <img
      src={src}
      alt={alt}
      title={alt}
      className="h-full w-full object-contain object-center"
      loading="lazy"
      referrerPolicy="no-referrer"
      onError={(event) => {
        const target = event.currentTarget as HTMLImageElement;
        if (target.src !== GROQ_LOGO_URL) {
          target.onerror = null;
          target.src = GROQ_LOGO_URL;
        }
      }}
    />
  );
}

function ModelSelect({ value, options, onChange }: { value: string; options: ModelOption[]; onChange: (value: string) => void }) {
  const [open, setOpen] = useState(false);
  const items = options.length ? options : [{ id: defaultModel, label: defaultModel.replace('groq/', ''), provider: 'groq', logo: 'groq' }];
  const selected = items.find((model) => model.id === value) ?? items[0];

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        className="flex h-12 w-full items-center gap-3 rounded-lg border border-hairline bg-surface px-4 text-left text-sm font-bold text-zinc-950 transition-colors hover:bg-surface-container-low focus:border-brand-primary focus:outline-none"
      >
        <span className="grid h-7 w-7 shrink-0 place-items-center overflow-hidden rounded-md border border-zinc-100 bg-white p-1 shadow-sm">
          <ModelLogo logo={selected.logo} provider={selected.provider} modelId={selected.id} />
        </span>
        <span className="min-w-0 flex-1 truncate">{selected.label}</span>
        <ChevronDown className={cn('h-4 w-4 text-on-surface-variant transition-transform', open && 'rotate-180')} />
      </button>
      {open && (
        <div className="absolute z-30 mt-2 max-h-80 w-full overflow-y-auto rounded-xl border border-hairline bg-white p-2 shadow-xl">
          {items.map((model) => (
            <button
              type="button"
              key={model.id}
              disabled={model.locked}
              onClick={() => {
                if (model.locked) return;
                onChange(model.id);
                setOpen(false);
              }}
              className={cn(
                'flex h-12 w-full items-center gap-3 rounded-lg px-3 text-left text-sm font-semibold transition-colors',
                model.id === selected.id ? 'bg-surface-container-low text-zinc-950' : 'text-on-surface-variant hover:bg-surface-container-low hover:text-zinc-950',
                model.locked && 'cursor-not-allowed opacity-40'
              )}
            >
              <span className="grid h-7 w-7 shrink-0 place-items-center overflow-hidden rounded-md border border-zinc-100 bg-white p-1 shadow-sm">
                <ModelLogo logo={model.logo} provider={model.provider} modelId={model.id} />
              </span>
              <span className="min-w-0 flex-1 truncate">{model.label}</span>
              {model.id === selected.id && <Check className="h-4 w-4 text-zinc-950" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function Agents() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const agentIdFromUrl = searchParams.get('agent');
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [documents, setDocuments] = useState<KnowledgeBase[]>([]);
  const [isLoading, setLoading] = useState(true);
  const [isSaving, setSaving] = useState(false);
  const [isCreating, setCreating] = useState(false);
  const [createStep, setCreateStep] = useState<CreateStep>('source');
  const [wizard, setWizard] = useState<WizardState>(() => initialWizard());
  const [createdAgent, setCreatedAgent] = useState<Agent | null>(null);
  const [editName, setEditName] = useState('');
  const [editInstructions, setEditInstructions] = useState('');
  const [editModel, setEditModel] = useState(defaultModel);
  const [models, setModels] = useState<ModelOption[]>([]);
  const [agentTab, setAgentTab] = useState<AgentTab>('playground');
  const [playgroundMessage, setPlaygroundMessage] = useState('What can you help me with?');
  const [sourceMode, setSourceMode] = useState<KnowledgeSourceMode>('url');
  const [sourceTitle, setSourceTitle] = useState('');
  const [sourceUrl, setSourceUrl] = useState('');
  const [sourceText, setSourceText] = useState('');
  const [sourceFile, setSourceFile] = useState<File | null>(null);
  const [isAddingSource, setAddingSource] = useState(false);
  const [playgroundMessages, setPlaygroundMessages] = useState<ChatMessage[]>([
    {
      id: 'intro',
      role: 'assistant',
      content: 'Ask a test question to preview how this agent responds using its instructions and sources.',
    },
  ]);
  const [isTesting, setTesting] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [deleteTarget, setDeleteTarget] = useState<Agent | null>(null);
  const [deleteKbTarget, setDeleteKbTarget] = useState<KnowledgeBase | null>(null);
  const [isFetchingBranding, setFetchingBranding] = useState(false);
  const [handoffEnabled, setHandoffEnabled] = useState(false);
  const [handoffDifficulty, setHandoffDifficulty] = useState<'easy' | 'balanced' | 'hard'>('balanced');
  const [handoffHasTeam, setHandoffHasTeam] = useState(false);
  const [handoffEffective, setHandoffEffective] = useState(false);
  const [handoffActiveCount, setHandoffActiveCount] = useState(0);
  const playgroundEndRef = useRef<HTMLDivElement | null>(null);

  const selectedAgent = useMemo(() => agents.find((agent) => agent.id === selectedId) ?? null, [agents, selectedId]);

  async function loadAgents() {
    setLoading(true);
    setError('');
    try {
      setAgents(await apiFetch<Agent[]>('/agents/'));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load agents');
    } finally {
      setLoading(false);
    }
  }

  async function loadModels() {
    try {
      const data = await apiFetch<{ models: ModelOption[] }>('/models/available');
      setModels(data.models);
    } catch {
      setModels([
        { id: defaultModel, label: defaultModel.replace('groq/', ''), provider: 'groq' },
      ]);
    }
  }

  async function loadAgentDetails(agentId: string) {
    setError('');
    try {
      const [kbData, settingsData] = await Promise.all([
        apiFetch<KnowledgeBase[]>(`/kb/${agentId}`),
        apiFetch<AgentSettingsResponse>(`/agents/${agentId}/settings`).catch(() => null),
      ]);
      setDocuments(kbData);
      if (settingsData?.widget) {
        setWizard((current) => ({
          ...current,
          theme: settingsData.widget.theme === 'dark' ? 'dark' : 'light',
          color: settingsData.widget.color,
          useColorHeader: settingsData.widget.use_color_header,
        }));
      }
      if (settingsData?.human_handoff) {
        setHandoffEnabled(settingsData.human_handoff.enabled);
        setHandoffDifficulty(settingsData.human_handoff.difficulty);
        setHandoffHasTeam(settingsData.human_handoff.has_team);
        setHandoffEffective(settingsData.human_handoff.effective);
        setHandoffActiveCount(settingsData.human_handoff.active_human_count);
      } else {
        setHandoffEnabled(false);
        setHandoffDifficulty('balanced');
        setHandoffHasTeam(false);
        setHandoffEffective(false);
        setHandoffActiveCount(0);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load agent details');
    }
  }

  useEffect(() => {
    loadAgents();
    loadModels();
  }, []);

  useEffect(() => {
    if (!agentIdFromUrl) return;
    setCreating(false);
    setSelectedId(agentIdFromUrl);
  }, [agentIdFromUrl]);

  useEffect(() => {
    if (!selectedAgent) return;
    setEditName(selectedAgent.name);
    setEditInstructions(selectedAgent.instructions ?? '');
    setEditModel(selectedAgent.model);
    setAgentTab('playground');
    setSourceMode('url');
    setSourceTitle('');
    setSourceUrl('');
    setSourceText('');
    setSourceFile(null);
    setPlaygroundMessages([
      {
        id: 'intro',
        role: 'assistant',
        content: 'Ask a test question to preview how this agent responds using its instructions and sources.',
      },
    ]);
    loadAgentDetails(selectedAgent.id);
  }, [selectedAgent?.id]);

  useEffect(() => {
    playgroundEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [playgroundMessages]);

  // Live branding fetch: shows favicon/logo immediately while typing website
  useEffect(() => {
    if (!isCreating) return;
    const source = !wizard.manual ? wizard.website.trim() : wizard.manualSource === 'website' ? wizard.manualUrl.trim() : '';
    if (!source || source.length < 4 || !source.includes('.')) return;
    const normalized = normalizeUrl(source);
    try {
      // basic URL validation - must be parseable after normalization
      new URL(normalized);
    } catch {
      return;
    }
    let cancelled = false;
    const timer = setTimeout(async () => {
      setFetchingBranding(true);
      try {
        const data = await apiFetch<{ logo_url?: string | null; favicon_url?: string | null; og_image_url?: string | null; theme_color?: string | null }>('/scrape/branding', {
          method: 'POST',
          body: JSON.stringify({ url: normalized }),
        });
        if (cancelled) return;
        const logo = data.logo_url || data.favicon_url || data.og_image_url || null;
        if (logo) {
          setWizard((prev) => ({ ...prev, logoUrl: logo }));
        }
        const theme = data.theme_color;
        if (theme && /^#[0-9A-Fa-f]{6}$/.test(theme)) {
          setWizard((prev) => {
            if (prev.color.toLowerCase() === '#ffffff') {
              return { ...prev, color: theme, useColorHeader: true };
            }
            return prev;
          });
        }
      } catch {
        // ignore branding fetch errors - keep initials
      } finally {
        if (!cancelled) setFetchingBranding(false);
      }
    }, 600);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [isCreating, wizard.website, wizard.manual, wizard.manualUrl, wizard.manualSource]);

  function startCreate() {
    setWizard(initialWizard());
    setCreatedAgent(null);
    setSelectedId(null);
    setDocuments([]);
    setEditModel(defaultModel);
    setCreateStep('source');
    setCreating(true);
    setError('');
    setNotice('');
  }

  async function addKnowledgeForAgent(agentId: string, createdName: string) {
    const jobs: Promise<unknown>[] = [];

    const addUrl = (url: string) => {
      const normalized = normalizeUrl(url);
      const body = new FormData();
      body.append('agent_id', agentId);
      body.append('source_type', 'url');
      body.append('url', normalized);
      jobs.push(apiFetch<KnowledgeBase>('/kb/add', { method: 'POST', body }));
    };

    const addText = (title: string, text: string) => {
      const body = new FormData();
      body.append('agent_id', agentId);
      body.append('source_type', 'text');
      body.append('title', title);
      body.append('structured_text', text);
      jobs.push(apiFetch<KnowledgeBase>('/kb/add', { method: 'POST', body }));
    };

    if (wizard.website.trim()) addUrl(wizard.website.trim());

    if (wizard.manual) {
      if (wizard.manualSource === 'website' && wizard.manualUrl.trim()) addUrl(wizard.manualUrl.trim());
      if (wizard.manualSource === 'text' && wizard.plainText.trim()) addText(`${createdName} notes`, wizard.plainText.trim());
      if (wizard.manualSource === 'qa' && wizard.qaText.trim()) addText(`${createdName} Q&A`, wizard.qaText.trim());
      if (wizard.manualSource === 'file' && wizard.file) {
        const body = new FormData();
        body.append('agent_id', agentId);
        const lowerName = wizard.file.name.toLowerCase();
        body.append('source_type', lowerName.endsWith('.pdf') ? 'upload_pdf' : lowerName.endsWith('.txt') ? 'upload_txt' : 'other');
        body.append('title', wizard.file.name);
        body.append('file', wizard.file);
        jobs.push(apiFetch<KnowledgeBase>('/kb/add', { method: 'POST', body }));
      }
    }

    await Promise.all(jobs);
  }

  async function trainAgent() {
    setSaving(true);
    setError('');
    setNotice('');
    try {
      const body = new FormData();
      body.append('name', wizard.name.trim());
      body.append('model', editModel || defaultModel);
      body.append('enable_retrieval', 'true');
      // Send website_url for favicon/brand auto-assignment (normalized, https auto-added)
      const websiteForBrand = wizard.website.trim() || (wizard.manual && wizard.manualSource === 'website' ? wizard.manualUrl.trim() : '');
      if (websiteForBrand) body.append('website_url', normalizeUrl(websiteForBrand));
      const agent = await apiFetch<Agent>('/agents/create', { method: 'POST', body });

      await addKnowledgeForAgent(agent.id, agent.name);
      await apiFetch(`/agents/${agent.id}/settings`, {
        method: 'PATCH',
        body: JSON.stringify({
          widget_theme: wizard.theme,
          widget_color: wizard.color,
          widget_use_color_header: wizard.useColorHeader,
          widget_greeting: `Hey, how can I help you today?`,
        }),
      });

      setCreatedAgent(agent);
      if (agent.avatar_url) {
        setWizard((prev) => ({ ...prev, logoUrl: agent.avatar_url }));
      }
      setAgents((current) => [agent, ...current]);
      await loadAgentDetails(agent.id);
      setNotice('Training started. You can continue while background indexing finishes.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create agent');
    } finally {
      setSaving(false);
    }
  }

  async function saveAppearance() {
    if (!createdAgent) return;
    setSaving(true);
    setError('');
    setNotice('');
    try {
      const updated = await apiFetch<{ agent: { name: string } }>(`/agents/${createdAgent.id}/settings`, {
        method: 'PATCH',
        body: JSON.stringify({
          name: wizard.name,
          model: editModel || defaultModel,
          widget_theme: wizard.theme,
          widget_color: wizard.color,
          widget_use_color_header: wizard.useColorHeader,
          widget_greeting: `Hey, how can I help you today?`,
        }),
      });

      const finalAgent = { ...createdAgent, name: updated.agent.name };
      setAgents((current) => current.map((agent) => (agent.id === finalAgent.id ? finalAgent : agent)));
      setCreatedAgent(null);
      setCreating(false);
      setSelectedId(finalAgent.id);
      setNotice('Agent appearance saved.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save appearance');
    } finally {
      setSaving(false);
    }
  }

  async function saveAgent() {
    if (!selectedAgent) return;
    setSaving(true);
    setError('');
    setNotice('');
    try {
      const updated = await apiFetch<{ agent: Partial<Agent> }>(`/agents/${selectedAgent.id}/settings`, {
        method: 'PATCH',
        body: JSON.stringify({
          name: editName,
          instructions: editInstructions,
          model: editModel || defaultModel,
          widget_theme: wizard.theme,
          widget_color: wizard.color,
          widget_use_color_header: wizard.useColorHeader,
          human_handoff_enabled: handoffEnabled,
          human_handoff_difficulty: handoffDifficulty,
        }),
      });
      setAgents((current) => current.map((agent) => (agent.id === selectedAgent.id ? { ...agent, ...updated.agent } : agent)));
      // refresh handoff meta after save
      try {
        const fresh = await apiFetch<AgentSettingsResponse>(`/agents/${selectedAgent.id}/settings`);
        if (fresh?.human_handoff) {
          setHandoffEnabled(fresh.human_handoff.enabled);
          setHandoffDifficulty(fresh.human_handoff.difficulty);
          setHandoffHasTeam(fresh.human_handoff.has_team);
          setHandoffEffective(fresh.human_handoff.effective);
          setHandoffActiveCount(fresh.human_handoff.active_human_count);
        }
      } catch {}
      setNotice('Agent settings saved.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save agent');
    } finally {
      setSaving(false);
    }
  }

  async function deleteAgent(agentId: string) {
    setSaving(true);
    setError('');
    try {
      await apiFetch(`/agents/${agentId}`, { method: 'DELETE' });
      setAgents((current) => current.filter((agent) => agent.id !== agentId));
      setSelectedId(null);
      setDocuments([]);
      setDeleteTarget(null);
      setNotice('Agent deleted.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not delete agent');
    } finally {
      setSaving(false);
    }
  }

  async function deleteKb(kbId: string) {
    if (!selectedAgent) return;
    try {
      await apiFetch(`/kb/${kbId}`, { method: 'DELETE' });
      setDocuments((current) => current.filter((doc) => doc.id !== kbId));
      setDeleteKbTarget(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not delete knowledge item');
    }
  }

  async function confirmDeleteKb() {
    if (!deleteKbTarget) return;
    await deleteKb(deleteKbTarget.id);
  }

  async function addKnowledgeSource() {
    if (!selectedAgent) return;
    setAddingSource(true);
    setError('');
    setNotice('');
    try {
      const body = new FormData();
      body.append('agent_id', selectedAgent.id);
      if (sourceTitle.trim()) body.append('title', sourceTitle.trim());

      if (sourceMode === 'url') {
        if (!sourceUrl.trim()) throw new Error('Enter a website URL.');
        body.append('source_type', 'url');
        body.append('url', normalizeUrl(sourceUrl.trim()));
      }

      if (sourceMode === 'text') {
        if (!sourceText.trim()) throw new Error('Enter knowledge base text.');
        body.append('source_type', 'text');
        body.append('structured_text', sourceText.trim());
      }

      if (sourceMode === 'file') {
        if (!sourceFile) throw new Error('Choose a file to upload.');
        const lowerName = sourceFile.name.toLowerCase();
        body.append('source_type', lowerName.endsWith('.pdf') ? 'upload_pdf' : lowerName.endsWith('.txt') ? 'upload_txt' : 'other');
        body.append('file', sourceFile);
      }

      await apiFetch<KnowledgeBase>('/kb/add', { method: 'POST', body });
      setSourceTitle('');
      setSourceUrl('');
      setSourceText('');
      setSourceFile(null);
      await loadAgentDetails(selectedAgent.id);
      setNotice('Knowledge source added. Indexing has started.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not add knowledge source');
    } finally {
      setAddingSource(false);
    }
  }

  async function retrainAllKnowledge() {
    if (!selectedAgent) return;
    setSaving(true);
    setError('');
    setNotice('');
    try {
      await apiFetch(`/kb/agent/${selectedAgent.id}/retrain`, { method: 'POST' });
      await loadAgentDetails(selectedAgent.id);
      setNotice('Retraining started for all knowledge sources.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not retrain knowledge sources');
    } finally {
      setSaving(false);
    }
  }

  async function reindexKb(kbId: string) {
    setError('');
    try {
      await apiFetch(`/kb/${kbId}/reindex`, { method: 'POST' });
      if (selectedAgent) await loadAgentDetails(selectedAgent.id);
      setNotice('Retraining started for this source.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not retrain source');
    }
  }

  async function testAgent() {
    if (!selectedAgent || !playgroundMessage.trim()) return;
    setTesting(true);
    const userMessage = playgroundMessage.trim();
    const userId = buildMessageId();
    const assistantId = buildMessageId();
    setPlaygroundMessages((current) => [
      ...current,
      { id: userId, role: 'user', content: userMessage },
      { id: assistantId, role: 'assistant', content: '', status: 'streaming' },
    ]);
    setPlaygroundMessage('');
    setError('');
    try {
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'}/chat/${selectedAgent.id}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('helpdeskai.access_token') ?? ''}`,
        },
        body: JSON.stringify({ message: userMessage }),
      });
      if (!response.ok || !response.body) throw new Error('Could not test this agent');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let answer = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split('\n\n');
        buffer = events.pop() ?? '';
        for (const event of events) {
          if (!event.includes('event: token')) continue;
          const dataLine = event.split('\n').find((line) => line.startsWith('data: '));
          if (!dataLine) continue;
          const payload = JSON.parse(dataLine.replace('data: ', ''));
          answer += payload.content ?? '';
          setPlaygroundMessages((current) => current.map((message) => (
            message.id === assistantId ? { ...message, content: answer, status: 'streaming' } : message
          )));
        }
      }
      if (!answer) {
        setPlaygroundMessages((current) => current.map((message) => (
          message.id === assistantId ? { ...message, content: 'The agent did not return a response.' } : message
        )));
      } else {
        setPlaygroundMessages((current) => current.map((message) => (
          message.id === assistantId ? { ...message, status: undefined } : message
        )));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not test this agent');
      setPlaygroundMessages((current) => current.map((message) => (
        message.status === 'streaming' ? { ...message, content: 'The playground could not reach the chat endpoint.', status: undefined } : message
      )));
    } finally {
      setTesting(false);
    }
  }

  if (isCreating) {
    const previewName = wizard.name || createdAgent?.name || 'Your Agent';
    const previewLogo = wizard.logoUrl || createdAgent?.avatar_url || null;
    const hasManualSource = (
      (wizard.manualSource === 'website' && wizard.manualUrl.trim()) ||
      (wizard.manualSource === 'file' && wizard.file) ||
      (wizard.manualSource === 'text' && wizard.plainText.trim()) ||
      (wizard.manualSource === 'qa' && wizard.qaText.trim())
    );
    const canTrain = Boolean(wizard.name.trim() && (wizard.manual ? hasManualSource : wizard.website.trim()));

    return (
      <AppLayout>
        <div className="max-w-[1440px] mx-auto">
          {(error || notice) && (
            <div className={cn('mb-6 rounded-lg border px-4 py-3 text-sm font-medium', error ? 'border-rose-200 bg-rose-50 text-rose-700' : 'border-emerald-200 bg-emerald-50 text-emerald-700')}>
              {error || notice}
            </div>
          )}

          {createStep === 'source' ? (
            <div className="grid min-h-[720px] grid-cols-1 lg:grid-cols-2 overflow-hidden rounded-xl border border-hairline bg-white">
              <section className="p-8 md:p-12 lg:p-16 flex flex-col justify-center">
                <button onClick={() => setCreating(false)} className="mb-10 inline-flex items-center gap-2 text-sm font-bold text-on-surface-variant hover:text-zinc-950">
                  <ChevronLeft className="w-4 h-4" />
                  Back to agents
                </button>
                <h1 className="text-3xl md:text-4xl font-semibold tracking-tight text-zinc-950">Create your AI agent</h1>
                <p className="mt-4 max-w-xl text-on-surface-variant">
                  Share your website link, and we'll automatically build an AI agent trained on your content.
                </p>

                <div className="mt-10 space-y-6">
                  <div className="space-y-2">
                    <label className="text-sm font-bold text-on-surface-variant">Agent name</label>
                    <input value={wizard.name} onChange={(event) => setWizard((current) => ({ ...current, name: event.target.value }))} placeholder="Frelo Esystems" className="h-12 w-full rounded-lg border border-hairline bg-surface px-4 text-sm focus:border-brand-primary focus:outline-none focus:ring-1 focus:ring-brand-primary" />
                  </div>
                  {!wizard.manual && (
                    <div className="space-y-2">
                      <label className="text-sm font-bold text-on-surface-variant">Website link</label>
                      <div className="relative">
                        <LinkIcon className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-on-surface-variant opacity-50" />
                        <input value={wizard.website} onChange={(event) => setWizard((current) => ({ ...current, website: event.target.value }))} placeholder="yourcompany.com" className="h-12 w-full rounded-lg border border-hairline bg-surface pl-11 pr-10 text-sm focus:border-brand-primary focus:outline-none focus:ring-1 focus:ring-brand-primary" />
                        {isFetchingBranding && (
                          <Loader2 className="absolute right-4 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-on-surface-variant opacity-60" />
                        )}
                      </div>
                      <p className="text-[10px] leading-none text-on-surface-variant opacity-60">You can enter just <span className="font-mono font-bold">yourcompany.com</span> or full <span className="font-mono font-bold">https://yourcompany.com</span> — https is added automatically.</p>
                    </div>
                  )}
                  <div className="space-y-2">
                    <label className="text-sm font-bold text-on-surface-variant">Use case</label>
                    <select value={wizard.useCase} onChange={(event) => setWizard((current) => ({ ...current, useCase: event.target.value }))} className="h-12 w-full rounded-lg border border-hairline bg-surface px-4 text-sm focus:border-brand-primary focus:outline-none focus:ring-1 focus:ring-brand-primary">
                      <option value="customer support agent">Customer support agent</option>
                    </select>
                  </div>

                  <button
                    onClick={() => setWizard((current) => ({ ...current, manual: !current.manual }))}
                    className="flex w-full items-center justify-between rounded-xl border border-hairline bg-surface p-4 text-left transition-colors hover:border-brand-primary hover:bg-surface-container-low"
                  >
                    <span>
                      <span className="block text-sm font-bold text-zinc-950">Set up manually with other sources</span>
                      <span className="mt-1 block text-xs text-on-surface-variant">{wizard.manual ? 'Manual sources are active. Website-only setup is hidden.' : 'Use files, text, Q&A, or a different website source.'}</span>
                    </span>
                    <ArrowRight className={cn('h-4 w-4 text-on-surface-variant transition-transform', wizard.manual && 'rotate-90 text-zinc-950')} />
                  </button>

                  {wizard.manual && (
                    <div className="space-y-5 rounded-xl border border-hairline bg-surface p-5">
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                        {[
                          ['website', 'Website'],
                          ['file', 'File/PDF'],
                          ['text', 'Plain text'],
                          ['qa', 'Q&A'],
                        ].map(([value, label]) => (
                          <button key={value} onClick={() => setWizard((current) => ({ ...current, manualSource: value as ManualSource }))} className={cn('h-10 rounded-lg border text-xs font-black uppercase tracking-widest transition-colors', wizard.manualSource === value ? 'border-brand-primary bg-zinc-950 text-white' : 'border-hairline bg-white text-on-surface-variant hover:text-zinc-950')}>
                            {label}
                          </button>
                        ))}
                      </div>

                      {wizard.manualSource === 'website' && (
                        <div className="relative">
                          <input value={wizard.manualUrl} onChange={(event) => setWizard((current) => ({ ...current, manualUrl: event.target.value }))} placeholder="docs.yourcompany.com" className="h-11 w-full rounded-lg border border-hairline bg-white px-4 pr-10 text-sm focus:border-brand-primary focus:outline-none" />
                          {isFetchingBranding && (
                            <Loader2 className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-on-surface-variant opacity-60" />
                          )}
                        </div>
                      )}
                      {wizard.manualSource === 'file' && (
                        <label className="flex min-h-28 cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-hairline bg-white text-center hover:border-brand-primary">
                          <input type="file" accept=".pdf,.txt,.doc,.docx,application/pdf,text/plain" onChange={(event) => setWizard((current) => ({ ...current, file: event.target.files?.[0] ?? null }))} className="hidden" />
                          <Upload className="mb-2 h-6 w-6 text-on-surface-variant" />
                          <span className="text-sm font-bold text-zinc-950">{wizard.file?.name || 'Upload document'}</span>
                          <span className="text-xs text-on-surface-variant">PDF, DOCX, TXT</span>
                        </label>
                      )}
                      {wizard.manualSource === 'text' && <textarea value={wizard.plainText} onChange={(event) => setWizard((current) => ({ ...current, plainText: event.target.value }))} rows={5} placeholder="Paste policies, product notes, FAQs, or support docs..." className="w-full resize-none rounded-lg border border-hairline bg-white p-4 text-sm focus:border-brand-primary focus:outline-none" />}
                      {wizard.manualSource === 'qa' && <textarea value={wizard.qaText} onChange={(event) => setWizard((current) => ({ ...current, qaText: event.target.value }))} rows={5} placeholder={'Q: How do I reset my password?\nA: Open Settings, then choose Reset password.'} className="w-full resize-none rounded-lg border border-hairline bg-white p-4 text-sm focus:border-brand-primary focus:outline-none" />}
                    </div>
                  )}

                  {!createdAgent ? (
                    <button onClick={trainAgent} disabled={isSaving || !canTrain} className="flex h-12 w-full items-center justify-center gap-2 rounded-lg bg-brand-primary px-6 text-sm font-bold text-brand-on-primary transition-opacity hover:opacity-90 disabled:opacity-50">
                      {isSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Bot className="h-4 w-4" />}
                      {isSaving ? 'Training agent...' : 'Train agent'}
                    </button>
                  ) : (
                    <button onClick={() => setCreateStep('appearance')} className="flex h-12 w-full items-center justify-center gap-2 rounded-lg bg-brand-primary px-6 text-sm font-bold text-brand-on-primary transition-opacity hover:opacity-90">
                      Continue
                      <ArrowRight className="h-4 w-4" />
                    </button>
                  )}
                </div>
              </section>

              <section className="hidden lg:flex items-center justify-center border-l border-hairline bg-[radial-gradient(#d9d9db_1.5px,transparent_1.5px)] [background-size:28px_28px] p-10">
                <div className="w-full max-w-md rounded-2xl bg-black p-5 text-white shadow-2xl">
                  <div className="flex items-center gap-3 border-b border-white/10 pb-4">
                    <div className="flex h-11 w-11 items-center justify-center overflow-hidden rounded-full bg-white text-black relative">
                      {isFetchingBranding && !previewLogo ? (
                        <Loader2 className="h-5 w-5 animate-spin text-zinc-400" />
                      ) : (
                        <AgentInitials name={previewName} image={previewLogo} />
                      )}
                    </div>
                    <div className="font-bold">{previewName}</div>
                    <MoreHorizontal className="ml-auto h-5 w-5" />
                  </div>
                  <div className="space-y-6 py-6">
                    <div className="max-w-[75%] rounded-2xl bg-zinc-900 p-4">
                      <div className="mb-2 flex items-center gap-2 font-bold">
                        <div className="h-7 w-7 overflow-hidden rounded-full bg-white text-black flex items-center justify-center"><AgentInitials name={previewName} image={previewLogo} /></div>
                        {previewName}
                      </div>
                      <p className="text-sm text-zinc-200">Hey, how can I help you today?</p>
                    </div>
                    <div className="ml-auto w-fit rounded-full bg-white px-5 py-3 text-sm text-black">I like AI agents</div>
                  </div>
                </div>
              </section>
            </div>
          ) : (
            <div className="grid min-h-[760px] grid-cols-1 lg:grid-cols-[1fr_1.15fr] overflow-hidden rounded-xl border border-hairline bg-white">
              <section className="p-8 md:p-12 lg:p-16">
                <h1 className="text-3xl font-semibold tracking-tight text-zinc-950">Agent's UI</h1>
                <p className="mt-3 max-w-xl text-on-surface-variant">Style your agent to match your brand. You can customize it further in the settings later.</p>

                <div className="mt-10 space-y-8">
                  <div className="space-y-2">
                    <label className="text-sm font-bold text-on-surface-variant">Agent name</label>
                    <input value={wizard.name} onChange={(event) => setWizard((current) => ({ ...current, name: event.target.value }))} className="h-12 w-full rounded-lg border border-hairline bg-surface px-4 text-sm focus:border-brand-primary focus:outline-none focus:ring-1 focus:ring-brand-primary" />
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-bold text-on-surface-variant">Model</label>
                    <ModelSelect value={editModel} options={models} onChange={setEditModel} />
                  </div>

                  <div className="border-t border-hairline pt-8">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-bold text-on-surface-variant">Appearance</span>
                      <div className="flex rounded-lg border border-hairline bg-surface p-1">
                        <button onClick={() => setWizard((current) => ({ ...current, theme: 'light' }))} className={cn('grid h-9 w-11 place-items-center rounded-md', wizard.theme === 'light' && 'bg-white shadow-sm')}><Sun className="h-4 w-4" /></button>
                        <button onClick={() => setWizard((current) => ({ ...current, theme: 'dark' }))} className={cn('grid h-9 w-11 place-items-center rounded-md', wizard.theme === 'dark' && 'bg-white shadow-sm')}><Moon className="h-4 w-4" /></button>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-sm font-bold text-on-surface-variant">Primary color</span>
                    <div className="flex items-center gap-3">
                      <label className="flex h-11 items-center gap-3 rounded-lg bg-surface px-3 font-mono text-sm font-bold">
                        <input type="color" value={wizard.color} onChange={(event) => setWizard((current) => ({ ...current, color: event.target.value }))} className="h-8 w-8 rounded border border-hairline" />
                        {wizard.color.toUpperCase()}
                      </label>
                      <button onClick={() => setWizard((current) => ({ ...current, color: '#ffffff' }))} className="grid h-11 w-11 place-items-center rounded-lg border border-hairline bg-surface"><RotateCcw className="h-4 w-4" /></button>
                    </div>
                  </div>

                  <label className="flex items-center justify-between">
                    <span className="text-sm font-bold text-on-surface-variant">Use primary color for header</span>
                    <input type="checkbox" checked={wizard.useColorHeader} onChange={(event) => setWizard((current) => ({ ...current, useColorHeader: event.target.checked }))} className="h-5 w-5 accent-brand-primary" />
                  </label>

                  <button onClick={saveAppearance} disabled={isSaving} className="flex h-12 w-full items-center justify-center gap-2 rounded-lg bg-brand-primary px-6 text-sm font-bold text-brand-on-primary transition-opacity hover:opacity-90 disabled:opacity-50">
                    {isSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                    Looks good
                  </button>
                </div>
              </section>

              <section className="flex items-start justify-center border-l border-hairline bg-[radial-gradient(#d9d9db_1.5px,transparent_1.5px)] [background-size:28px_28px] px-8 py-20">
                <div className="h-[680px] w-full max-w-[520px] overflow-hidden rounded-2xl bg-black text-white shadow-2xl">
                  <div className="flex h-24 items-center gap-4 px-7" style={{ backgroundColor: wizard.useColorHeader ? wizard.color : '#1c1c1f', color: wizard.useColorHeader && wizard.color.toLowerCase() === '#ffffff' ? '#000' : '#fff' }}>
                    <div className="h-12 w-12 overflow-hidden rounded-full bg-white text-black flex items-center justify-center"><AgentInitials name={previewName} image={previewLogo} /></div>
                    <div className="text-lg font-bold">{previewName}</div>
                    <MoreHorizontal className="ml-auto h-6 w-6" />
                  </div>
                  <div className={cn('h-full p-7', wizard.theme === 'light' ? 'bg-white text-black' : 'bg-black text-white')}>
                    <div className={cn('max-w-[72%] rounded-2xl p-5', wizard.theme === 'light' ? 'bg-zinc-100' : 'bg-zinc-900')}>
                      <div className="mb-3 flex items-center gap-3 font-bold">
                        <div className="h-8 w-8 overflow-hidden rounded-full bg-white text-black flex items-center justify-center"><AgentInitials name={previewName} image={previewLogo} /></div>
                        {previewName}
                      </div>
                      <p className="text-sm opacity-80">Hey, how can I help you today?</p>
                    </div>
                    <div className="ml-auto mt-7 w-fit rounded-full px-6 py-4 text-sm" style={{ backgroundColor: wizard.color, color: wizard.color.toLowerCase() === '#ffffff' ? '#111' : '#fff' }}>I like AI Agents</div>
                  </div>
                </div>
              </section>
            </div>
          )}
        </div>
      </AppLayout>
    );
  }

  if (selectedAgent) {
    const readySources = documents.filter((doc) => doc.status === 'ready').length;
    const tabs: Array<{ id: AgentTab; label: string; icon: typeof MessageCircle }> = [
      { id: 'playground', label: 'Playground', icon: MessageCircle },
      { id: 'sources', label: 'Sources', icon: Database },
      { id: 'settings', label: 'Settings', icon: Settings },
    ];
    return (
      <AppLayout>
        <div className="space-y-6">
          <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <button onClick={() => setSelectedId(null)} className="grid h-10 w-10 shrink-0 place-items-center rounded-lg border border-zinc-200 bg-white text-zinc-600 transition-colors hover:text-zinc-900" aria-label="Back to agents">
                <ChevronLeft className="h-5 w-5" />
              </button>
              <div className="flex min-w-0 items-center gap-3">
                <div className="grid h-10 w-10 shrink-0 place-items-center overflow-hidden rounded-lg bg-zinc-900 text-white">
                  <AgentInitials name={selectedAgent.name} image={selectedAgent.avatar_url} />
                </div>
                <div className="min-w-0">
                  <h1 className="truncate text-xl font-semibold tracking-tight text-zinc-950">{selectedAgent.name}</h1>
                  <p className="truncate text-sm text-zinc-500">{readySources} ready source{readySources === 1 ? '' : 's'} · {formatModelLabel(selectedAgent.model)}</p>
                </div>
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <button onClick={() => navigate(`/agents/${selectedAgent.id}/deploy`)} className="inline-flex h-10 items-center gap-2 rounded-lg border border-zinc-200 bg-white px-4 text-sm font-medium text-zinc-900 transition-colors hover:bg-zinc-50">
                <Code2 className="h-4 w-4" /> Deploy
              </button>
              <button onClick={() => setDeleteTarget(selectedAgent)} disabled={isSaving} className="inline-flex h-10 items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 text-sm font-medium text-zinc-900 transition-colors hover:bg-zinc-50" aria-label="Delete agent">
                <Trash2 className="h-4 w-4" />
              </button>
              <button onClick={saveAgent} disabled={isSaving || !editName.trim()} className="inline-flex h-10 items-center gap-2 rounded-lg bg-zinc-900 px-5 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:opacity-50">
                {isSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Save
              </button>
            </div>
          </header>

          {deleteTarget && (
            <div className="fixed inset-0 z-[80] flex items-center justify-center bg-zinc-950/45 px-4 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="delete-agent-title">
              <div className="w-full max-w-md rounded-2xl border border-hairline bg-white p-6 shadow-2xl">
                <div className="flex items-start gap-4">
                  <div className="grid h-11 w-11 shrink-0 place-items-center rounded-lg bg-rose-50 text-rose-700">
                    <Trash2 className="h-5 w-5" />
                  </div>
                  <div className="min-w-0">
                    <h2 id="delete-agent-title" className="text-lg font-semibold text-zinc-950">Delete agent?</h2>
                    <p className="mt-2 text-sm leading-6 text-zinc-600">
                      This will delete <span className="font-semibold text-zinc-950">{deleteTarget.name}</span> and its configuration. This action cannot be undone.
                    </p>
                  </div>
                </div>
                <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
                  <button type="button" onClick={() => setDeleteTarget(null)} disabled={isSaving} className="h-10 rounded-lg border border-zinc-200 bg-white px-4 text-sm font-medium text-zinc-900 hover:bg-zinc-50 disabled:opacity-50">
                    Cancel
                  </button>
                  <button type="button" onClick={() => deleteAgent(deleteTarget.id)} disabled={isSaving} className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-rose-600 px-4 text-sm font-medium text-white hover:bg-rose-700 disabled:opacity-50">
                    {isSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                    Delete agent
                  </button>
                </div>
              </div>
            </div>
          )}

          {deleteKbTarget && (
            <div className="fixed inset-0 z-[80] flex items-center justify-center bg-zinc-950/45 px-4 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="delete-kb-title">
              <div className="w-full max-w-md rounded-2xl border border-hairline bg-white p-6 shadow-2xl">
                <div className="flex items-start gap-4">
                  <div className="grid h-11 w-11 shrink-0 place-items-center rounded-lg bg-rose-50 text-rose-700">
                    <Trash2 className="h-5 w-5" />
                  </div>
                  <div className="min-w-0">
                    <h2 id="delete-kb-title" className="text-lg font-semibold text-zinc-950">Delete knowledge source?</h2>
                    <p className="mt-2 text-sm leading-6 text-zinc-600">
                      This will delete <span className="font-semibold text-zinc-950">{deleteKbTarget.title || deleteKbTarget.source_uri || 'this source'}</span>.
                    </p>
                  </div>
                </div>
                <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
                  <button type="button" onClick={() => setDeleteKbTarget(null)} className="h-10 rounded-lg border border-zinc-200 bg-white px-4 text-sm font-medium text-zinc-900 hover:bg-zinc-50">
                    Cancel
                  </button>
                  <button type="button" onClick={confirmDeleteKb} className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-rose-600 px-4 text-sm font-medium text-white hover:bg-rose-700">
                    <Trash2 className="h-4 w-4" />
                    Delete source
                  </button>
                </div>
              </div>
            </div>
          )}

          {(error || notice) && <div className={cn('rounded-lg border px-4 py-3 text-sm font-medium', error ? 'border-rose-200 bg-rose-50 text-rose-700' : 'border-emerald-200 bg-emerald-50 text-emerald-700')}>{error || notice}</div>}

          <div className="flex gap-1 border-b border-zinc-200">
            {tabs.map((tab) => (
              <button key={tab.id} onClick={() => setAgentTab(tab.id)} className={cn('inline-flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors', agentTab === tab.id ? 'border-zinc-900 text-zinc-900' : 'border-transparent text-zinc-500 hover:text-zinc-900')}>
                <tab.icon className="h-4 w-4" /> {tab.label}
              </button>
            ))}
          </div>

          {agentTab === 'playground' && (
            <div className="mx-auto flex max-w-[560px] flex-col items-center">
              <div className={cn('h-[680px] w-full overflow-hidden rounded-3xl border border-zinc-200 shadow-2xl', wizard.theme === 'light' ? 'bg-white text-black' : 'bg-zinc-950 text-white')}>
                <div className="flex h-20 items-center gap-4 px-6" style={{ backgroundColor: wizard.useColorHeader ? wizard.color : wizard.theme === 'light' ? '#f4f4f5' : '#18181b', color: wizard.useColorHeader && wizard.color.toLowerCase() === '#ffffff' ? '#111' : undefined }}>
                  <div className="h-11 w-11 overflow-hidden rounded-full bg-white text-black flex items-center justify-center"><AgentInitials name={editName || selectedAgent.name} image={selectedAgent.avatar_url} /></div>
                  <div className="text-lg font-semibold">{editName || selectedAgent.name}</div>
                  <RefreshCw className="ml-auto h-5 w-5 text-zinc-300" />
                </div>
                <div className="flex h-[calc(100%-5rem)] flex-col">
                  <div className="flex-1 space-y-4 overflow-y-auto px-6 py-5">
                    {playgroundMessages.map((message) => (
                      <div key={message.id} className={cn('flex', message.role === 'user' ? 'justify-end' : 'justify-start')}>
                        <div className={cn('max-w-[78%] rounded-2xl px-4 py-3 text-sm shadow-sm', message.role === 'user' ? 'bg-zinc-900 text-white' : wizard.theme === 'light' ? 'bg-zinc-100 text-zinc-900' : 'bg-zinc-900 text-zinc-100')}>
                          {message.role === 'assistant' ? (
                            <div className="space-y-3">
                              <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                                {message.content || (message.status === 'streaming' ? 'Thinking...' : '')}
                              </ReactMarkdown>
                              {message.status !== 'streaming' && (
                                <div className="mt-2 flex items-center gap-3 text-[10px] uppercase tracking-widest opacity-50">
                                  <span>Just now</span>
                                  <span>|</span>
                                  <span>Sources: {readySources}</span>
                                </div>
                              )}
                            </div>
                          ) : (
                            <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>
                          )}
                        </div>
                      </div>
                    ))}
                    <div ref={playgroundEndRef} />
                  </div>
                  <div className={cn('mx-6 mb-6 flex h-14 items-center gap-3 rounded-full border px-4', wizard.theme === 'light' ? 'border-zinc-200 bg-white' : 'border-zinc-700 bg-zinc-950')}>
                    <input value={playgroundMessage} onChange={(event) => setPlaygroundMessage(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') testAgent(); }} placeholder="Message..." className={cn('min-w-0 flex-1 bg-transparent text-sm outline-none', wizard.theme === 'light' ? 'text-black placeholder:text-zinc-400' : 'text-white placeholder:text-zinc-500')} />
                    <button onClick={testAgent} disabled={isTesting} className="grid h-10 w-10 place-items-center rounded-full bg-zinc-900 text-white disabled:opacity-50">{isTesting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}</button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {agentTab === 'sources' && (
            <section className="mx-auto max-w-4xl overflow-hidden rounded-2xl border border-hairline bg-white">
              <div className="flex items-center justify-between border-b border-zinc-100 px-6 py-4">
                <h2 className="text-sm font-semibold text-zinc-950">Data sources ({documents.length})</h2>
                <div className="flex items-center gap-2">
                  <button onClick={retrainAllKnowledge} disabled={isSaving || documents.length === 0} className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs font-medium text-zinc-900 disabled:opacity-50 hover:bg-zinc-50"><RotateCcw className="h-4 w-4" />Retrain all</button>
                  <button onClick={() => selectedAgent && loadAgentDetails(selectedAgent.id)} className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs font-medium text-zinc-900 hover:bg-zinc-50"><RefreshCw className="h-4 w-4" />Refresh</button>
                </div>
              </div>
              <div className="border-b border-zinc-100 p-5">
                <div className="space-y-4">
                  <div>
                    <p className="text-sm font-semibold text-zinc-950">Add a source</p>
                    <p className="mt-0.5 text-xs text-zinc-500">Pick a type, paste or upload, then press Add. Indexing starts right away.</p>
                  </div>
                  <div className="flex rounded-lg border border-zinc-200 bg-zinc-50 p-1">
                    {[
                      ['url', 'URL', LinkIcon],
                      ['file', 'File', Upload],
                      ['text', 'Text', FileText],
                    ].map(([value, label, Icon]) => (
                      <button key={value as string} type="button" onClick={() => setSourceMode(value as KnowledgeSourceMode)} className={cn('flex flex-1 items-center justify-center gap-2 rounded-md px-3 py-2 text-xs font-medium transition-colors', sourceMode === value ? 'bg-zinc-900 text-white' : 'text-zinc-500 hover:text-zinc-900')}>
                        <Icon className="h-4 w-4" />
                        {label as string}
                      </button>
                    ))}
                  </div>
                  <input value={sourceTitle} onChange={(event) => setSourceTitle(event.target.value)} placeholder="Source title (optional)" className="h-11 rounded-lg border border-zinc-200 bg-white px-4 text-sm outline-none focus:border-zinc-900" />
                  {sourceMode === 'url' && (
                    <div className="space-y-1">
                      <input value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} placeholder="example.com/help" className="h-11 w-full rounded-lg border border-zinc-200 bg-white px-4 text-sm outline-none focus:border-zinc-900" />
                      <p className="text-[10px] text-zinc-400">https:// is optional — we'll add it if missing.</p>
                    </div>
                  )}
                  {sourceMode === 'file' && (
                    <label className="flex min-h-24 cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed border-zinc-300 bg-zinc-50 px-4 text-center text-sm font-medium text-zinc-600 hover:border-zinc-900 hover:text-zinc-900">
                      <Upload className="mb-2 h-5 w-5" />
                      {sourceFile ? sourceFile.name : 'Choose PDF, TXT, DOCX, or another text file'}
                      <input type="file" className="hidden" onChange={(event) => setSourceFile(event.target.files?.[0] ?? null)} />
                    </label>
                  )}
                  {sourceMode === 'text' && (
                    <textarea value={sourceText} onChange={(event) => setSourceText(event.target.value)} placeholder="Paste knowledge base text..." rows={6} className="w-full resize-none rounded-lg border border-zinc-200 bg-white p-4 text-sm outline-none focus:border-zinc-900" />
                  )}
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <button onClick={addKnowledgeSource} disabled={isAddingSource} className="inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-zinc-900 px-5 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50">
                      {isAddingSource ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                      Add source
                    </button>
                    <span className="text-xs text-zinc-500">URL, PDF, TXT, DOCX supported.</span>
                  </div>
                </div>
              </div>
              <div className="divide-y divide-zinc-100">
                {documents.length === 0 && <div className="px-6 py-10 text-sm text-zinc-500">No knowledge sources yet.</div>}
                {documents.map((doc) => (
                  <div key={doc.id} className="flex flex-col justify-between gap-4 px-6 py-4 md:flex-row md:items-center">
                    <div className="flex min-w-0 items-center gap-4">
                      <div className="grid h-10 w-10 shrink-0 place-items-center rounded-lg border border-zinc-200 bg-zinc-50 text-zinc-600">{doc.source_type === 'url' ? <LinkIcon className="h-5 w-5" /> : <FileText className="h-5 w-5" />}</div>
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-zinc-900">{doc.title || doc.source_uri || 'Untitled knowledge'}</p>
                        <p className="text-[11px] font-medium text-zinc-400">{sourceLabel(doc.source_type)} · Added {formatRelative(doc.created_at)}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className={cn('rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide', doc.status === 'ready' && 'bg-emerald-100 text-emerald-700', doc.status === 'pending' && 'bg-amber-100 text-amber-700', doc.status === 'failed' && 'bg-rose-100 text-rose-700')}>{doc.status}</span>
                      <button onClick={() => reindexKb(doc.id)} className="rounded-lg border border-zinc-200 px-3 py-2 text-xs font-medium text-zinc-900 hover:bg-zinc-50">Retrain</button>
                      <button onClick={() => setDeleteKbTarget(doc)} className="text-zinc-400 transition-colors hover:text-rose-500" aria-label="Delete knowledge source"><Trash2 className="h-4 w-4" /></button>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {agentTab === 'settings' && (
            <div className="mx-auto max-w-3xl space-y-6">
              <section className="rounded-2xl border border-hairline bg-white p-6">
                <h2 className="text-sm font-semibold text-zinc-950">General</h2>
                <p className="mt-0.5 text-xs text-zinc-500">Name, model, and behavior for this agent.</p>
                <div className="mt-5 grid gap-5 sm:grid-cols-2">
                  <label className="block space-y-2">
                    <span className="text-xs font-medium text-zinc-700">Agent name</span>
                    <input value={editName} onChange={(event) => setEditName(event.target.value)} className="h-11 w-full rounded-lg border border-zinc-200 bg-white px-3 text-sm focus:border-zinc-900 focus:outline-none" />
                  </label>
                  <label className="block space-y-2">
                    <span className="text-xs font-medium text-zinc-700">Model</span>
                    <ModelSelect value={editModel} options={models} onChange={setEditModel} />
                  </label>
                </div>
                <label className="mt-5 block space-y-2">
                  <span className="text-xs font-medium text-zinc-700">Instructions</span>
                  <textarea rows={10} value={editInstructions} onChange={(event) => setEditInstructions(event.target.value)} className="w-full resize-none rounded-lg border border-zinc-200 bg-zinc-50 p-4 font-mono text-xs leading-relaxed focus:border-zinc-900 focus:outline-none" />
                </label>
              </section>

              <section className="rounded-2xl border border-hairline bg-white p-6">
                <h2 className="text-sm font-semibold text-zinc-950">Appearance</h2>
                <p className="mt-0.5 text-xs text-zinc-500">How the chat widget looks for visitors.</p>
                <div className="mt-5 grid gap-5 sm:grid-cols-2">
                  <div className="space-y-2">
                    <span className="text-xs font-medium text-zinc-700">Theme</span>
                    <div className="flex rounded-lg border border-zinc-200 bg-zinc-50 p-1">
                      <button type="button" onClick={() => setWizard((current) => ({ ...current, theme: 'light' }))} className={cn('flex flex-1 items-center justify-center gap-2 rounded-md py-2 text-sm font-medium', wizard.theme === 'light' ? 'bg-white text-zinc-900 shadow-sm' : 'text-zinc-500')}><Sun className="h-4 w-4" /> Light</button>
                      <button type="button" onClick={() => setWizard((current) => ({ ...current, theme: 'dark' }))} className={cn('flex flex-1 items-center justify-center gap-2 rounded-md py-2 text-sm font-medium', wizard.theme === 'dark' ? 'bg-white text-zinc-900 shadow-sm' : 'text-zinc-500')}><Moon className="h-4 w-4" /> Dark</button>
                    </div>
                  </div>
                  <div className="space-y-2">
                    <span className="text-xs font-medium text-zinc-700">Primary color</span>
                    <label className="flex h-11 items-center gap-3 rounded-lg border border-zinc-200 bg-white px-3">
                      <input type="color" value={wizard.color} onChange={(event) => setWizard((current) => ({ ...current, color: event.target.value }))} className="h-7 w-8 rounded border border-zinc-200" />
                      <span className="font-mono text-sm text-zinc-900">{wizard.color.toUpperCase()}</span>
                    </label>
                  </div>
                </div>
                <label className="mt-5 flex items-center justify-between rounded-lg border border-zinc-200 bg-zinc-50 px-4 py-3">
                  <span className="text-sm font-medium text-zinc-700">Use primary color for header</span>
                  <input type="checkbox" checked={wizard.useColorHeader} onChange={(event) => setWizard((current) => ({ ...current, useColorHeader: event.target.checked }))} className="h-5 w-5 rounded accent-zinc-900" />
                </label>
              </section>

              <section className="overflow-hidden rounded-2xl border border-hairline bg-white">
                <div className="flex items-center justify-between border-b border-zinc-100 px-6 py-4">
                  <div className="flex items-center gap-3">
                    <div className="grid h-10 w-10 place-items-center rounded-xl bg-zinc-900 text-white">
                      <Handshake className="h-5 w-5" />
                    </div>
                    <div>
                      <h3 className="text-sm font-semibold text-zinc-950">Human handoff</h3>
                      <p className="text-xs text-zinc-500">Decide when your AI should bring a person in.</p>
                    </div>
                  </div>
                  <span className={cn('rounded-full px-2.5 py-1 text-[11px] font-semibold', handoffEffective ? 'bg-zinc-900 text-white' : 'bg-zinc-100 text-zinc-600')}>
                    {handoffEffective ? 'Live' : handoffEnabled ? 'On · idle' : 'Off'}
                  </span>
                </div>

                <div className="space-y-5 px-6 py-5">
                  <div className="flex items-center justify-between rounded-2xl border border-hairline bg-zinc-50 p-4">
                    <div className="min-w-0">
                      <div className="text-sm font-medium text-zinc-900">Enable handoff</div>
                      <div className="text-xs text-zinc-500">
                        {handoffHasTeam ? `${handoffActiveCount} active team member${handoffActiveCount === 1 ? '' : 's'} assigned` : 'No team assigned — assign in Team page'}
                      </div>
                    </div>
                    <button type="button" role="switch" aria-checked={handoffEnabled} onClick={() => { const next = !handoffEnabled; setHandoffEnabled(next); setHandoffEffective(next && handoffHasTeam); }} className={cn('relative h-6 w-11 shrink-0 rounded-full transition-colors', handoffEnabled ? 'bg-zinc-900' : 'bg-zinc-300')}>
                      <span className={cn('absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform', handoffEnabled && 'translate-x-5')} />
                    </button>
                  </div>

                  {!handoffHasTeam ? (
                    <div className="flex items-start gap-3 rounded-2xl border border-hairline bg-zinc-50 px-4 py-3">
                      <Users className="mt-0.5 h-4 w-4 shrink-0 text-zinc-500" />
                      <div className="text-xs leading-relaxed text-zinc-600">
                        <span className="font-semibold text-zinc-900">No team on this agent.</span> You can turn handoff on, but it stays idle until you assign an active human in <button onClick={() => navigate('/team')} className="font-semibold underline underline-offset-4">Team</button>. {handoffEnabled ? 'Turn on now, assign later — it will become live automatically.' : ''}
                      </div>
                    </div>
                  ) : !handoffEffective && handoffEnabled ? (
                    <div className="flex items-start gap-3 rounded-2xl border border-hairline bg-zinc-50 px-4 py-3">
                      <Users className="mt-0.5 h-4 w-4 shrink-0 text-zinc-500" />
                      <div className="text-xs leading-relaxed text-zinc-600">
                        Handoff is <span className="font-semibold text-zinc-900">on but idle</span> — no human is online for this agent right now. Visitors will see fallback email.
                      </div>
                    </div>
                  ) : null}

                  <div className={cn('space-y-3', !handoffEnabled && 'pointer-events-none opacity-50')}>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-semibold uppercase tracking-wider text-zinc-500">Eagerness</span>
                      <span className="text-[11px] text-zinc-400">· how quickly the AI offers a human</span>
                    </div>
                    <div className="grid grid-cols-3 gap-2">
                      {[
                        { id: 'easy', label: 'Easy', sub: 'Quick', icon: Zap, desc: 'One hint, then offer' },
                        { id: 'balanced', label: 'Balanced', sub: 'Thoughtful', icon: Handshake, desc: '1–2 tries, then offer' },
                        { id: 'hard', label: 'Hard', sub: 'Persistent', icon: ShieldCheck, desc: 'Insist twice' },
                      ].map((opt) => {
                        const active = handoffDifficulty === opt.id;
                        return (
                          <button key={opt.id} type="button" disabled={!handoffEnabled} onClick={() => setHandoffDifficulty(opt.id as any)} className={cn('flex flex-col items-start gap-1.5 rounded-xl border p-3 text-left transition-all', active ? 'border-zinc-900 bg-zinc-900 text-white' : 'border-zinc-200 bg-white text-zinc-900 hover:border-zinc-400', !handoffEnabled && 'cursor-not-allowed')}>
                            <opt.icon className="h-4 w-4" />
                            <span className="text-xs font-semibold leading-none">{opt.label}</span>
                            <span className={cn('text-[10px] font-medium uppercase tracking-wide', active ? 'text-white/70' : 'text-zinc-500')}>{opt.sub}</span>
                            <span className={cn('text-[11px] leading-tight', active ? 'text-white/90' : 'text-zinc-500')}>{opt.desc}</span>
                            {active && <span className="mt-1 inline-flex items-center gap-1 rounded-full bg-white px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-zinc-900"><Check className="h-3 w-3" /> Active</span>}
                          </button>
                        );
                      })}
                    </div>

                    <div className="rounded-2xl border border-hairline bg-zinc-50 p-3">
                      <div className="text-xs font-semibold text-zinc-900">
                        {handoffDifficulty === 'easy' ? 'Easy — AI is generous' : handoffDifficulty === 'hard' ? 'Hard — AI is persistent' : 'Balanced — AI is thoughtful'}
                      </div>
                      <p className="mt-1 text-xs leading-relaxed text-zinc-600">
                        {handoffDifficulty === 'easy' && 'After one brief try or any hint of wanting a human, the AI will offer to connect you. Best for high-touch support.'}
                        {handoffDifficulty === 'balanced' && 'The AI tries one or two helpful steps, asks a clarifying question, then offers a human if still stuck. The default.'}
                        {handoffDifficulty === 'hard' && 'The AI exhausts its knowledge, asks 2–3 questions, and only hands off if the visitor insists twice. Best for deflecting easy tickets.'}
                      </p>
                    </div>
                  </div>

                  <p className="text-xs leading-relaxed text-zinc-500">
                    {handoffEffective ? 'Live — visitors can be connected right now.' : handoffEnabled ? 'On but idle — handoff activates once a teammate is online.' : 'Off — the AI answers alone and never triggers the connecting flow.'}
                  </p>
                </div>
              </section>
            </div>
          )}
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <div className="space-y-8">
        <header className="flex flex-col justify-between gap-4 border-b border-hairline pb-6 sm:flex-row sm:items-end">
          <div>
            <h1 className="text-3xl font-semibold tracking-[-0.03em] text-zinc-950 md:text-4xl">
              Your <span className="font-display-italic text-[1.1em]">agents</span>
            </h1>
            <p className="mt-2 text-[15px] text-zinc-500">Train, test, and deploy AI agents for your customers.</p>
          </div>
          <button onClick={startCreate} className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-zinc-950 px-4 text-sm font-medium text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.12),0_1px_2px_rgba(0,0,0,0.2)] transition-colors hover:bg-zinc-800"><Plus className="h-4 w-4" />New agent</button>
        </header>

        {error && <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-medium text-rose-700">{error}</div>}

        {isLoading ? (
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 6 }).map((_, index) => (
              <div key={`agent-skeleton-${index}`} className="overflow-hidden rounded-2xl border border-hairline bg-white">
                <div className="h-44 animate-pulse bg-zinc-100" />
                <div className="space-y-2 p-4">
                  <div className="h-4 w-2/3 animate-pulse rounded-full bg-zinc-100" />
                  <div className="h-3 w-1/3 animate-pulse rounded-full bg-zinc-100" />
                </div>
              </div>
            ))}
          </div>
        ) : agents.length === 0 ? (
          <div className="relative overflow-hidden rounded-2xl border border-hairline bg-white px-6 py-16 text-center">
            <div className="mx-auto grid h-12 w-12 place-items-center rounded-xl border border-hairline bg-white shadow-soft">
              <Bot className="h-5 w-5 text-zinc-900" />
            </div>
            <h2 className="mt-5 text-2xl font-semibold tracking-tight text-zinc-950">
              Create your first <span className="font-display-italic text-[1.1em]">agent</span>
            </h2>
            <p className="mx-auto mt-2 max-w-md text-[15px] text-zinc-500">Start with a website link or set it up manually with files, plain text, and Q&A.</p>
            <button onClick={startCreate} className="mt-7 inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-zinc-950 px-4 text-sm font-medium text-white transition-colors hover:bg-zinc-800"><Plus className="h-4 w-4" />New agent</button>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-3">
            {agents.map((agent) => (
              <motion.div key={agent.id} whileHover={{ y: -2 }} transition={{ duration: 0.2 }} onClick={() => setSelectedId(agent.id)} className="group cursor-pointer overflow-hidden rounded-2xl border border-hairline bg-white transition-shadow hover:shadow-[0_12px_32px_-12px_rgba(0,0,0,0.18)]">
                <div className="relative grid h-44 place-items-center overflow-hidden border-b border-hairline bg-zinc-50">
                  <div className="absolute inset-0 bg-[radial-gradient(#e4e4e7_1px,transparent_1px)] [background-size:14px_14px] opacity-70" aria-hidden />
                  <div className="relative w-[70%] rounded-xl border border-hairline bg-white p-3 shadow-soft transition-transform duration-300 group-hover:-translate-y-1">
                    <div className="flex items-center gap-2">
                      <div className="grid h-6 w-6 shrink-0 place-items-center overflow-hidden rounded-full bg-zinc-950 text-[10px] text-white">
                        <AgentInitials name={agent.name} image={agent.avatar_url} />
                      </div>
                      <div className="h-2 w-16 rounded-full bg-zinc-200" />
                    </div>
                    <div className="mt-3 h-2 w-[85%] rounded-full bg-zinc-100" />
                    <div className="mt-1.5 h-2 w-[60%] rounded-full bg-zinc-100" />
                    <div className="mt-3 ml-auto h-5 w-[55%] rounded-lg bg-zinc-950" />
                  </div>
                </div>
                <div className="flex items-center gap-3 px-4 py-3.5">
                  <div className="min-w-0 flex-1">
                    <h3 className="truncate text-[15px] font-medium text-zinc-950">{agent.name}</h3>
                    <p className="mt-0.5 truncate text-[13px] text-zinc-500">{formatModelLabel(agent.model)}</p>
                  </div>
                  <ArrowRight className="h-4 w-4 shrink-0 text-zinc-300 transition-all group-hover:translate-x-0.5 group-hover:text-zinc-900" />
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </div>
    </AppLayout>
  );
}
