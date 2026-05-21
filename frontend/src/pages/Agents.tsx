import {
  ArrowRight,
  Bot,
  Check,
  ChevronDown,
  ChevronLeft,
  Code2,
  FileText,
  Link as LinkIcon,
  Loader2,
  MessageCircle,
  Moon,
  MoreHorizontal,
  Plus,
  RotateCcw,
  Save,
  Settings,
  Sun,
  Trash2,
  Upload,
  RefreshCw,
  Send,
  X,
} from 'lucide-react';
import { AppLayout } from '../components/Layout';
import { cn } from '../lib/utils';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { motion } from 'motion/react';
import { Agent, apiFetch, formatRelative, KnowledgeBase } from '../lib/api';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const defaultModel = 'groq/openai/gpt-oss-20b';

type CreateStep = 'source' | 'appearance';
type ManualSource = 'website' | 'file' | 'text' | 'qa';

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
};

type AgentSettingsResponse = {
  widget: {
    theme: 'light' | 'dark' | 'auto';
    color: string;
    position: string;
    greeting: string;
    use_color_header: boolean;
  };
};

type ModelOption = {
  id: string;
  label: string;
  provider: string;
  logo?: string;
  locked?: boolean;
};

type AgentTab = 'playground' | 'sources';

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

const markdownComponents = {
  h1: ({ children }: { children: React.ReactNode }) => <h1 className="text-lg font-bold text-brand-primary">{children}</h1>,
  h2: ({ children }: { children: React.ReactNode }) => <h2 className="text-base font-bold text-brand-primary">{children}</h2>,
  h3: ({ children }: { children: React.ReactNode }) => <h3 className="text-sm font-bold text-brand-primary">{children}</h3>,
  p: ({ children }: { children: React.ReactNode }) => <p className="text-sm leading-relaxed text-on-surface-variant">{children}</p>,
  ul: ({ children }: { children: React.ReactNode }) => <ul className="ml-5 list-disc space-y-2 text-sm text-on-surface-variant">{children}</ul>,
  ol: ({ children }: { children: React.ReactNode }) => <ol className="ml-5 list-decimal space-y-2 text-sm text-on-surface-variant">{children}</ol>,
  li: ({ children }: { children: React.ReactNode }) => <li className="leading-relaxed">{children}</li>,
  a: ({ children, href }: { children: React.ReactNode; href?: string }) => (
    <a href={href} className="font-semibold text-brand-primary underline decoration-brand-primary/40 underline-offset-4" target="_blank" rel="noreferrer">
      {children}
    </a>
  ),
  strong: ({ children }: { children: React.ReactNode }) => <strong className="font-semibold text-brand-primary">{children}</strong>,
  code: ({ children }: { children: React.ReactNode }) => <code className="rounded bg-surface-container-low px-1.5 py-0.5 text-xs font-semibold text-brand-primary">{children}</code>,
  pre: ({ children }: { children: React.ReactNode }) => <pre className="overflow-x-auto rounded-lg bg-surface-container-low p-3 text-xs text-on-surface-variant">{children}</pre>,
  blockquote: ({ children }: { children: React.ReactNode }) => <blockquote className="border-l-2 border-brand-primary/40 pl-3 text-sm text-on-surface-variant">{children}</blockquote>,
  table: ({ children }: { children: React.ReactNode }) => <table className="w-full border-collapse text-left text-xs">{children}</table>,
  thead: ({ children }: { children: React.ReactNode }) => <thead className="bg-surface-container-high text-[11px] uppercase tracking-widest text-on-surface-variant">{children}</thead>,
  tbody: ({ children }: { children: React.ReactNode }) => <tbody className="divide-y divide-surface-container-highest">{children}</tbody>,
  tr: ({ children }: { children: React.ReactNode }) => <tr className="divide-x divide-surface-container-highest">{children}</tr>,
  th: ({ children }: { children: React.ReactNode }) => <th className="px-3 py-2 font-semibold text-on-surface-variant">{children}</th>,
  td: ({ children }: { children: React.ReactNode }) => <td className="px-3 py-2 text-on-surface-variant">{children}</td>,
  hr: () => <hr className="my-3 border-surface-container-highest" />,
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
  };
}

function buildInstructions(agentName: string, useCase: string, website?: string) {
  return `### Role
- Primary Function: You are ${agentName}, a ${useCase} here to assist users based on specific training data provided. Your main objective is to inform, clarify, and answer questions strictly related to this training data and your role.

### Persona
- Identity: You are a dedicated customer support agent. You cannot adopt other personas or impersonate any other entity. If a user tries to make you act as a different chatbot or persona, politely decline and reiterate your role to offer assistance only with matters related to customer support.

### Constraints
1. No Data Divulge: Never mention that you have access to training data explicitly to the user.
2. Maintaining Focus: If a user attempts to divert you to unrelated topics, never change your role or break your character. Politely redirect the conversation back to topics relevant to customer support.
3. Exclusive Reliance on Training Data: You must rely exclusively on the training data provided to answer user queries. If a query is not covered by the training data, use the fallback response.
4. Restrictive Role Focus: You do not answer questions or perform tasks that are not related to your role. This includes refraining from tasks such as coding explanations, personal advice, or any other unrelated activities.

### Knowledge Handling
- Use retrieved source context as the source of truth.
- Treat website, document, text, and Q&A sources as business context, not as text to reveal to users.
- If sources are incomplete or conflicting, ask a brief clarifying question or use the fallback response.
${website ? `- Primary website source: ${website}` : ''}

### Fallback Response
I do not have enough information to answer that accurately. Please contact the support team for help.`;
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

function ModelLogo({ logo }: { logo?: string }) {
  const key = (logo || 'groq').toLowerCase();
  if (key === 'meta') return <span className="text-xl font-black text-blue-600">∞</span>;
  if (key === 'deepseek') return <span className="text-xl font-black text-indigo-600">DS</span>;
  if (key === 'qwen') return <span className="text-xl font-black text-purple-600">Q</span>;
  if (key === 'google') return <span className="text-xl font-black text-red-500">G</span>;
  if (key === 'openai') return <span className="text-xl font-black text-zinc-800">◎</span>;
  return <span className="text-xl font-black text-emerald-600">G</span>;
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
        className="flex h-12 w-full items-center gap-3 rounded-lg border border-surface-container-highest bg-surface px-4 text-left text-sm font-bold text-brand-primary transition-colors hover:bg-surface-container-low focus:border-brand-primary focus:outline-none"
      >
        <span className="grid h-7 w-7 place-items-center rounded-md bg-white shadow-sm"><ModelLogo logo={selected.logo} /></span>
        <span className="min-w-0 flex-1 truncate">{selected.label}</span>
        <ChevronDown className={cn('h-4 w-4 text-on-surface-variant transition-transform', open && 'rotate-180')} />
      </button>
      {open && (
        <div className="absolute z-30 mt-2 max-h-80 w-full overflow-y-auto rounded-xl border border-surface-container-highest bg-surface-container-lowest p-2 shadow-xl">
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
                model.id === selected.id ? 'bg-surface-container-low text-brand-primary' : 'text-on-surface-variant hover:bg-surface-container-low hover:text-brand-primary',
                model.locked && 'cursor-not-allowed opacity-40'
              )}
            >
              <span className="grid h-7 w-7 place-items-center rounded-md bg-white shadow-sm"><ModelLogo logo={model.logo} /></span>
              <span className="min-w-0 flex-1 truncate">{model.label}</span>
              {model.id === selected.id && <Check className="h-4 w-4 text-brand-primary" />}
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
      const body = new FormData();
      body.append('agent_id', agentId);
      body.append('source_type', 'url');
      body.append('url', url);
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
      body.append('instructions', buildInstructions(wizard.name.trim(), wizard.useCase, wizard.website.trim()));
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
        }),
      });
      setAgents((current) => current.map((agent) => (agent.id === selectedAgent.id ? { ...agent, ...updated.agent } : agent)));
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
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not delete knowledge item');
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
            <div className="grid min-h-[720px] grid-cols-1 lg:grid-cols-2 overflow-hidden rounded-xl border border-surface-container-highest bg-surface-container-lowest">
              <section className="p-8 md:p-12 lg:p-16 flex flex-col justify-center">
                <button onClick={() => setCreating(false)} className="mb-10 inline-flex items-center gap-2 text-sm font-bold text-on-surface-variant hover:text-brand-primary">
                  <ChevronLeft className="w-4 h-4" />
                  Back to agents
                </button>
                <h1 className="text-3xl md:text-4xl font-bold tracking-tight text-brand-primary">Create your AI agent</h1>
                <p className="mt-4 max-w-xl text-on-surface-variant">
                  Share your website link, and we'll automatically build an AI agent trained on your content.
                </p>

                <div className="mt-10 space-y-6">
                  <div className="space-y-2">
                    <label className="text-sm font-bold text-on-surface-variant">Agent name</label>
                    <input value={wizard.name} onChange={(event) => setWizard((current) => ({ ...current, name: event.target.value }))} placeholder="Frelo Esystems" className="h-12 w-full rounded-lg border border-surface-container-highest bg-surface px-4 text-sm focus:border-brand-primary focus:outline-none focus:ring-1 focus:ring-brand-primary" />
                  </div>
                  {!wizard.manual && (
                    <div className="space-y-2">
                      <label className="text-sm font-bold text-on-surface-variant">Website link</label>
                      <div className="relative">
                        <LinkIcon className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-on-surface-variant opacity-50" />
                        <input value={wizard.website} onChange={(event) => setWizard((current) => ({ ...current, website: event.target.value }))} placeholder="https://yourcompany.com" className="h-12 w-full rounded-lg border border-surface-container-highest bg-surface pl-11 pr-4 text-sm focus:border-brand-primary focus:outline-none focus:ring-1 focus:ring-brand-primary" />
                      </div>
                    </div>
                  )}
                  <div className="space-y-2">
                    <label className="text-sm font-bold text-on-surface-variant">Use case</label>
                    <select value={wizard.useCase} onChange={(event) => setWizard((current) => ({ ...current, useCase: event.target.value }))} className="h-12 w-full rounded-lg border border-surface-container-highest bg-surface px-4 text-sm focus:border-brand-primary focus:outline-none focus:ring-1 focus:ring-brand-primary">
                      <option value="customer support agent">Customer support agent</option>
                    </select>
                  </div>

                  <button
                    onClick={() => setWizard((current) => ({ ...current, manual: !current.manual }))}
                    className="flex w-full items-center justify-between rounded-xl border border-surface-container-highest bg-surface p-4 text-left transition-colors hover:border-brand-primary hover:bg-surface-container-low"
                  >
                    <span>
                      <span className="block text-sm font-bold text-brand-primary">Set up manually with other sources</span>
                      <span className="mt-1 block text-xs text-on-surface-variant">{wizard.manual ? 'Manual sources are active. Website-only setup is hidden.' : 'Use files, text, Q&A, or a different website source.'}</span>
                    </span>
                    <ArrowRight className={cn('h-4 w-4 text-on-surface-variant transition-transform', wizard.manual && 'rotate-90 text-brand-primary')} />
                  </button>

                  {wizard.manual && (
                    <div className="space-y-5 rounded-xl border border-surface-container-highest bg-surface p-5">
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                        {[
                          ['website', 'Website'],
                          ['file', 'File/PDF'],
                          ['text', 'Plain text'],
                          ['qa', 'Q&A'],
                        ].map(([value, label]) => (
                          <button key={value} onClick={() => setWizard((current) => ({ ...current, manualSource: value as ManualSource }))} className={cn('h-10 rounded-lg border text-xs font-black uppercase tracking-widest transition-colors', wizard.manualSource === value ? 'border-brand-primary bg-brand-primary text-brand-on-primary' : 'border-surface-container-highest bg-surface-container-lowest text-on-surface-variant hover:text-brand-primary')}>
                            {label}
                          </button>
                        ))}
                      </div>

                      {wizard.manualSource === 'website' && <input value={wizard.manualUrl} onChange={(event) => setWizard((current) => ({ ...current, manualUrl: event.target.value }))} placeholder="https://docs.yourcompany.com" className="h-11 w-full rounded-lg border border-surface-container-highest bg-surface-container-lowest px-4 text-sm focus:border-brand-primary focus:outline-none" />}
                      {wizard.manualSource === 'file' && (
                        <label className="flex min-h-28 cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-surface-container-highest bg-surface-container-lowest text-center hover:border-brand-primary">
                          <input type="file" accept=".pdf,.txt,.doc,.docx,application/pdf,text/plain" onChange={(event) => setWizard((current) => ({ ...current, file: event.target.files?.[0] ?? null }))} className="hidden" />
                          <Upload className="mb-2 h-6 w-6 text-on-surface-variant" />
                          <span className="text-sm font-bold text-brand-primary">{wizard.file?.name || 'Upload document'}</span>
                          <span className="text-xs text-on-surface-variant">PDF, DOCX, TXT</span>
                        </label>
                      )}
                      {wizard.manualSource === 'text' && <textarea value={wizard.plainText} onChange={(event) => setWizard((current) => ({ ...current, plainText: event.target.value }))} rows={5} placeholder="Paste policies, product notes, FAQs, or support docs..." className="w-full resize-none rounded-lg border border-surface-container-highest bg-surface-container-lowest p-4 text-sm focus:border-brand-primary focus:outline-none" />}
                      {wizard.manualSource === 'qa' && <textarea value={wizard.qaText} onChange={(event) => setWizard((current) => ({ ...current, qaText: event.target.value }))} rows={5} placeholder={'Q: How do I reset my password?\nA: Open Settings, then choose Reset password.'} className="w-full resize-none rounded-lg border border-surface-container-highest bg-surface-container-lowest p-4 text-sm focus:border-brand-primary focus:outline-none" />}
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

              <section className="hidden lg:flex items-center justify-center border-l border-surface-container-highest bg-[radial-gradient(#d9d9db_1.5px,transparent_1.5px)] [background-size:28px_28px] p-10">
                <div className="w-full max-w-md rounded-2xl bg-black p-5 text-white shadow-2xl">
                  <div className="flex items-center gap-3 border-b border-white/10 pb-4">
                    <div className="flex h-11 w-11 items-center justify-center overflow-hidden rounded-full bg-white text-black">
                      <AgentInitials name={previewName} />
                    </div>
                    <div className="font-bold">{previewName}</div>
                    <MoreHorizontal className="ml-auto h-5 w-5" />
                  </div>
                  <div className="space-y-6 py-6">
                    <div className="max-w-[75%] rounded-2xl bg-zinc-900 p-4">
                      <div className="mb-2 flex items-center gap-2 font-bold">
                        <div className="h-7 w-7 overflow-hidden rounded-full bg-white text-black flex items-center justify-center"><AgentInitials name={previewName} /></div>
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
            <div className="grid min-h-[760px] grid-cols-1 lg:grid-cols-[1fr_1.15fr] overflow-hidden rounded-xl border border-surface-container-highest bg-surface-container-lowest">
              <section className="p-8 md:p-12 lg:p-16">
                <h1 className="text-3xl font-bold tracking-tight text-brand-primary">Agent's UI</h1>
                <p className="mt-3 max-w-xl text-on-surface-variant">Style your agent to match your brand. You can customize it further in the settings later.</p>

                <div className="mt-10 space-y-8">
                  <div className="space-y-2">
                    <label className="text-sm font-bold text-on-surface-variant">Agent name</label>
                    <input value={wizard.name} onChange={(event) => setWizard((current) => ({ ...current, name: event.target.value }))} className="h-12 w-full rounded-lg border border-surface-container-highest bg-surface px-4 text-sm focus:border-brand-primary focus:outline-none focus:ring-1 focus:ring-brand-primary" />
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-bold text-on-surface-variant">Model</label>
                    <ModelSelect value={editModel} options={models} onChange={setEditModel} />
                  </div>

                  <div className="border-t border-surface-container-highest pt-8">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-bold text-on-surface-variant">Appearance</span>
                      <div className="flex rounded-lg border border-surface-container-highest bg-surface p-1">
                        <button onClick={() => setWizard((current) => ({ ...current, theme: 'light' }))} className={cn('grid h-9 w-11 place-items-center rounded-md', wizard.theme === 'light' && 'bg-white shadow-sm')}><Sun className="h-4 w-4" /></button>
                        <button onClick={() => setWizard((current) => ({ ...current, theme: 'dark' }))} className={cn('grid h-9 w-11 place-items-center rounded-md', wizard.theme === 'dark' && 'bg-white shadow-sm')}><Moon className="h-4 w-4" /></button>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-sm font-bold text-on-surface-variant">Primary color</span>
                    <div className="flex items-center gap-3">
                      <label className="flex h-11 items-center gap-3 rounded-lg bg-surface px-3 font-mono text-sm font-bold">
                        <input type="color" value={wizard.color} onChange={(event) => setWizard((current) => ({ ...current, color: event.target.value }))} className="h-8 w-8 rounded border border-surface-container-highest" />
                        {wizard.color.toUpperCase()}
                      </label>
                      <button onClick={() => setWizard((current) => ({ ...current, color: '#ffffff' }))} className="grid h-11 w-11 place-items-center rounded-lg border border-surface-container-highest bg-surface"><RotateCcw className="h-4 w-4" /></button>
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

              <section className="flex items-start justify-center border-l border-surface-container-highest bg-[radial-gradient(#d9d9db_1.5px,transparent_1.5px)] [background-size:28px_28px] px-8 py-20">
                <div className="h-[680px] w-full max-w-[520px] overflow-hidden rounded-2xl bg-black text-white shadow-2xl">
                  <div className="flex h-24 items-center gap-4 px-7" style={{ backgroundColor: wizard.useColorHeader ? wizard.color : '#1c1c1f', color: wizard.useColorHeader && wizard.color.toLowerCase() === '#ffffff' ? '#000' : '#fff' }}>
                    <div className="h-12 w-12 overflow-hidden rounded-full bg-white text-black flex items-center justify-center"><AgentInitials name={previewName} /></div>
                    <div className="text-lg font-bold">{previewName}</div>
                    <MoreHorizontal className="ml-auto h-6 w-6" />
                  </div>
                  <div className={cn('h-full p-7', wizard.theme === 'light' ? 'bg-white text-black' : 'bg-black text-white')}>
                    <div className={cn('max-w-[72%] rounded-2xl p-5', wizard.theme === 'light' ? 'bg-zinc-100' : 'bg-zinc-900')}>
                      <div className="mb-3 flex items-center gap-3 font-bold">
                        <div className="h-8 w-8 overflow-hidden rounded-full bg-white text-black flex items-center justify-center"><AgentInitials name={previewName} /></div>
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
    return (
      <AppLayout>
        <div className="min-h-[calc(100vh-8rem)]">
          <header className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <button onClick={() => setSelectedId(null)} className="p-2 -ml-2 rounded-full hover:bg-surface-container-low transition-colors" aria-label="Back to agents"><ChevronLeft className="w-6 h-6 text-brand-primary" /></button>
              <div>
                <h1 className="text-2xl md:text-3xl font-bold tracking-tight text-brand-primary">{selectedAgent.name}</h1>
                <p className="text-on-surface-variant mt-1 text-sm">Playground, configuration, sources, and deployment.</p>
              </div>
            </div>
            <div className="flex gap-3">
              <button onClick={() => navigate(`/agents/${selectedAgent.id}/deploy`)} className="flex items-center justify-center gap-2 px-4 py-2 border border-surface-container-highest bg-surface-container-low text-brand-primary text-sm font-bold rounded-lg hover:bg-surface-container transition-colors"><Code2 className="w-4 h-4" />Deploy</button>
              <button onClick={() => deleteAgent(selectedAgent.id)} disabled={isSaving} className="flex items-center justify-center gap-2 px-4 py-2 border border-rose-200 bg-rose-50 text-rose-700 text-sm font-bold rounded-lg hover:bg-rose-100 transition-colors"><Trash2 className="w-4 h-4" />Delete</button>
              <button onClick={saveAgent} disabled={isSaving || !editName.trim()} className="flex items-center justify-center gap-2 px-6 py-2 bg-brand-primary text-brand-on-primary text-sm font-bold rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50">{isSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}Save</button>
            </div>
          </header>

          {(error || notice) && <div className={cn('rounded-lg border px-4 py-3 text-sm font-medium', error ? 'border-rose-200 bg-rose-50 text-rose-700' : 'border-emerald-200 bg-emerald-50 text-emerald-700')}>{error || notice}</div>}

          <div className="mt-6 grid grid-cols-1 lg:grid-cols-[380px_1fr] gap-8 items-start">
            <aside className="space-y-6">
              <div className="flex rounded-lg border border-surface-container-highest bg-surface-container-lowest p-1">
                {[
                  ['playground', 'Playground'],
                  ['sources', 'Sources'],
                ].map(([value, label]) => (
                  <button key={value} onClick={() => setAgentTab(value as AgentTab)} className={cn('flex-1 rounded-md px-3 py-2 text-xs font-black uppercase tracking-widest transition-colors', agentTab === value ? 'bg-brand-primary text-brand-on-primary' : 'text-on-surface-variant hover:text-brand-primary')}>
                    {label}
                  </button>
                ))}
              </div>

              <section className="bg-surface-container-lowest border border-surface-container-highest p-6 rounded-xl shadow-sm">
                <div className="rounded-lg bg-surface-container-low p-4">
                  <div className="flex items-center gap-2 text-lg font-bold text-emerald-700"><span className="h-2 w-2 rounded-full bg-emerald-600" />Trained</div>
                  <p className="mt-2 text-sm font-medium text-on-surface-variant">{readySources} ready sources • {documents.length} total</p>
                </div>

                <div className="mt-6 space-y-5">
                  <label className="block space-y-2">
                    <span className="text-xs font-black uppercase tracking-widest text-on-surface-variant">Agent name</span>
                    <input value={editName} onChange={(event) => setEditName(event.target.value)} className="w-full h-11 px-4 bg-surface-container-low border border-surface-container-highest rounded-lg text-sm focus:outline-none focus:border-brand-primary" />
                  </label>

                  <label className="block space-y-2">
                    <span className="text-xs font-black uppercase tracking-widest text-on-surface-variant">Model</span>
                    <ModelSelect value={editModel} options={models} onChange={setEditModel} />
                  </label>

                  <div className="space-y-4 rounded-lg border border-surface-container-highest bg-surface-container-low p-4">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-black uppercase tracking-widest text-on-surface-variant">Agent UI</span>
                      <div className="flex rounded-lg border border-surface-container-highest bg-surface p-1">
                        <button type="button" onClick={() => setWizard((current) => ({ ...current, theme: 'light' }))} className={cn('grid h-8 w-10 place-items-center rounded-md', wizard.theme === 'light' && 'bg-white shadow-sm')} aria-label="Light appearance"><Sun className="h-4 w-4" /></button>
                        <button type="button" onClick={() => setWizard((current) => ({ ...current, theme: 'dark' }))} className={cn('grid h-8 w-10 place-items-center rounded-md', wizard.theme === 'dark' && 'bg-white shadow-sm')} aria-label="Dark appearance"><Moon className="h-4 w-4" /></button>
                      </div>
                    </div>
                    <div className="flex items-center justify-between gap-4">
                      <span className="text-sm font-bold text-on-surface-variant">Primary color</span>
                      <label className="flex h-10 items-center gap-2 rounded-lg bg-surface px-2 font-mono text-xs font-bold">
                        <input type="color" value={wizard.color} onChange={(event) => setWizard((current) => ({ ...current, color: event.target.value }))} className="h-7 w-7 rounded border border-surface-container-highest" />
                        {wizard.color.toUpperCase()}
                      </label>
                    </div>
                    <label className="flex items-center justify-between gap-4">
                      <span className="text-sm font-bold text-on-surface-variant">Use color for header</span>
                      <input type="checkbox" checked={wizard.useColorHeader} onChange={(event) => setWizard((current) => ({ ...current, useColorHeader: event.target.checked }))} className="h-5 w-5 accent-brand-primary" />
                    </label>
                  </div>

                  <label className="block space-y-2">
                    <span className="text-xs font-black uppercase tracking-widest text-on-surface-variant">Instructions (System prompt)</span>
                    <textarea rows={14} value={editInstructions} onChange={(event) => setEditInstructions(event.target.value)} className="w-full p-4 bg-surface-container-low border border-surface-container-highest rounded-lg text-xs font-mono focus:outline-none focus:border-brand-primary resize-none leading-relaxed" />
                  </label>
                </div>
              </section>
            </aside>

            <main className="min-h-[760px] rounded-xl border border-surface-container-highest bg-[radial-gradient(#d9d9db_1.5px,transparent_1.5px)] [background-size:28px_28px] p-4 md:p-8">
              {agentTab === 'playground' && (
                <div className="mx-auto flex max-w-[560px] flex-col items-center gap-6">
                  <div className={cn('h-[680px] w-full overflow-hidden rounded-[28px] shadow-2xl', wizard.theme === 'light' ? 'bg-white text-black' : 'bg-black text-white')}>
                    <div className="flex h-20 items-center gap-4 px-6" style={{ backgroundColor: wizard.useColorHeader ? wizard.color : wizard.theme === 'light' ? '#f4f4f5' : '#18181b', color: wizard.useColorHeader && wizard.color.toLowerCase() === '#ffffff' ? '#111' : undefined }}>
                      <div className="h-11 w-11 overflow-hidden rounded-full bg-white text-black flex items-center justify-center"><AgentInitials name={editName || selectedAgent.name} image={selectedAgent.avatar_url} /></div>
                      <div className="text-lg font-bold">{editName || selectedAgent.name}</div>
                      <RefreshCw className="ml-auto h-5 w-5 text-zinc-300" />
                    </div>
                    <div className="flex h-[calc(100%-5rem)] flex-col">
                      <div className="flex-1 space-y-4 overflow-y-auto px-6 py-5">
                        {playgroundMessages.map((message) => (
                          <div key={message.id} className={cn('flex', message.role === 'user' ? 'justify-end' : 'justify-start')}>
                            <div className={cn(
                              'max-w-[78%] rounded-2xl px-4 py-3 text-sm shadow-sm',
                              message.role === 'user'
                                ? 'bg-brand-primary text-brand-on-primary'
                                : wizard.theme === 'light'
                                  ? 'bg-zinc-100 text-zinc-900'
                                  : 'bg-zinc-900 text-zinc-100'
                            )}>
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
                      <div className={cn('mx-6 mb-6 flex h-14 items-center gap-3 rounded-full border px-4', wizard.theme === 'light' ? 'border-zinc-200 bg-white' : 'border-zinc-700 bg-black')}>
                        <input
                          value={playgroundMessage}
                          onChange={(event) => setPlaygroundMessage(event.target.value)}
                          onKeyDown={(event) => { if (event.key === 'Enter') testAgent(); }}
                          placeholder="Message..."
                          className={cn('min-w-0 flex-1 bg-transparent text-sm outline-none', wizard.theme === 'light' ? 'text-black placeholder:text-zinc-400' : 'text-white placeholder:text-zinc-500')}
                        />
                        <button onClick={testAgent} disabled={isTesting} className="grid h-10 w-10 place-items-center rounded-full disabled:opacity-50" style={{ backgroundColor: wizard.color, color: wizard.color.toLowerCase() === '#ffffff' ? '#111' : '#fff' }}>{isTesting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}</button>
                      </div>
                    </div>
                  </div>
                  <button onClick={() => setAgentTab('sources')} className="h-12 w-full max-w-[560px] rounded-lg border border-surface-container-highest bg-surface-container-lowest text-sm font-bold text-on-surface-variant hover:text-brand-primary">Show sources</button>
                </div>
              )}

              {agentTab === 'sources' && (
                <section className="mx-auto max-w-4xl rounded-xl bg-surface-container-lowest border border-surface-container-highest overflow-hidden">
                  <div className="flex items-center justify-between border-b border-surface-container-highest bg-surface-container-low px-6 py-4">
                    <h2 className="text-sm font-black uppercase tracking-widest text-brand-primary">Data Sources ({documents.length})</h2>
                    <button onClick={() => selectedAgent && loadAgentDetails(selectedAgent.id)} className="flex items-center gap-2 rounded-lg border border-surface-container-highest bg-surface px-3 py-2 text-xs font-bold text-brand-primary"><RefreshCw className="h-4 w-4" />Refresh</button>
                  </div>
                  <div className="divide-y divide-surface-container-highest">
                    {documents.length === 0 && <div className="px-6 py-10 text-sm text-on-surface-variant">No knowledge sources yet.</div>}
                    {documents.map((doc) => (
                      <div key={doc.id} className="px-6 py-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
                        <div className="flex items-center gap-4 min-w-0">
                          <div className="w-10 h-10 bg-surface-container rounded-lg flex items-center justify-center text-on-surface-variant border border-surface-container-highest shrink-0">{doc.source_type === 'url' ? <LinkIcon className="w-5 h-5" /> : <FileText className="w-5 h-5" />}</div>
                          <div className="min-w-0">
                            <p className="text-sm font-bold text-brand-primary truncate">{doc.title || doc.source_uri || 'Untitled knowledge'}</p>
                            <p className="text-[10px] uppercase font-bold tracking-wider text-on-surface-variant opacity-60">{sourceLabel(doc.source_type)} • Added {formatRelative(doc.created_at)}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className={cn('px-2 py-1 text-[10px] font-black rounded-lg border shadow-sm uppercase', doc.status === 'ready' && 'bg-emerald-500 text-white border-emerald-600', doc.status === 'pending' && 'bg-amber-500 text-white border-amber-600', doc.status === 'failed' && 'bg-rose-500 text-white border-rose-600')}>{doc.status}</span>
                          <button onClick={() => reindexKb(doc.id)} className="rounded-lg border border-surface-container-highest px-3 py-2 text-xs font-bold text-brand-primary hover:bg-surface-container-low">Retrain</button>
                          <button onClick={() => deleteKb(doc.id)} className="text-on-surface-variant hover:text-rose-500 transition-colors" aria-label="Delete knowledge source"><Trash2 className="w-4 h-4" /></button>
                        </div>
                      </div>
                    ))}
                  </div>
                </section>
              )}
            </main>
          </div>
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <div className="space-y-8 md:space-y-12">
        <header className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-brand-primary">My Agents</h1>
            <p className="text-on-surface-variant mt-1 text-sm">Deploy and manage your support agents.</p>
          </div>
          <button onClick={startCreate} className="flex items-center justify-center gap-2 px-6 py-3 bg-brand-primary text-brand-on-primary text-sm font-bold rounded-lg hover:opacity-90 transition-opacity"><Plus className="w-4 h-4" />Create New Agent</button>
        </header>

        {error && <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-medium text-rose-700">{error}</div>}

        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
            {Array.from({ length: 6 }).map((_, index) => (
              <div key={`agent-skeleton-${index}`} className="overflow-hidden rounded-2xl border border-surface-container-highest bg-surface-container-lowest shadow-sm">
                <div className="h-40 bg-surface-container-low">
                  <div className="h-full w-full animate-pulse bg-[radial-gradient(circle_at_top,#e4e4e7_1px,transparent_1px)] [background-size:16px_16px]" />
                </div>
                <div className="space-y-3 p-5">
                  <div className="h-4 w-2/3 rounded-full bg-surface-container-high animate-pulse" />
                  <div className="h-3 w-1/2 rounded-full bg-surface-container-high animate-pulse" />
                  <div className="h-10 w-full rounded-xl bg-surface-container-high animate-pulse" />
                </div>
              </div>
            ))}
          </div>
        ) : agents.length === 0 ? (
          <div className="border border-surface-container-highest bg-surface-container-lowest rounded-xl p-10 text-center">
            <Bot className="w-10 h-10 mx-auto text-on-surface-variant mb-4" />
            <h2 className="text-xl font-bold text-brand-primary">Create your first support agent</h2>
            <p className="text-sm text-on-surface-variant mt-2 max-w-md mx-auto">Start with a website link or set it up manually with files, plain text, and Q&A.</p>
            <button onClick={startCreate} className="mt-6 inline-flex items-center justify-center gap-2 px-6 py-3 bg-brand-primary text-brand-on-primary text-sm font-bold rounded-lg hover:opacity-90 transition-opacity"><Plus className="w-4 h-4" />Create Agent</button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
            {agents.map((agent) => (
              <motion.div key={agent.id} whileHover={{ y: -4 }} onClick={() => setSelectedId(agent.id)} className="group relative cursor-pointer overflow-hidden rounded-2xl border border-surface-container-highest bg-surface-container-lowest shadow-sm transition-all hover:border-brand-primary">
                <div className="relative flex h-40 flex-col overflow-hidden border-b border-surface-container-highest">
                  <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,#d4d4d8_1px,transparent_1px)] [background-size:18px_18px]" />
                  <div className="absolute inset-0 bg-gradient-to-br from-brand-primary/10 via-transparent to-emerald-500/10" />
                  <div className="relative z-10 flex items-start justify-between p-5">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="h-11 w-11 rounded-full bg-brand-primary text-brand-on-primary flex items-center justify-center overflow-hidden border border-white/30">
                        <AgentInitials name={agent.name} image={agent.avatar_url} />
                      </div>
                      <div className="min-w-0">
                        <div className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant">Support agent</div>
                        <h3 className="truncate text-lg font-bold text-brand-primary">{agent.name}</h3>
                      </div>
                    </div>
                    <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-[10px] font-black uppercase tracking-widest text-emerald-700">Ready</span>
                  </div>
                  <div className="relative z-10 mt-auto px-5 pb-5">
                    <div className="flex flex-wrap gap-2">
                      <span className="rounded-full border border-surface-container-highest bg-surface-container-lowest px-3 py-1 text-[10px] font-black uppercase tracking-widest text-on-surface-variant">Model {formatModelLabel(agent.model)}</span>
                      <span className="rounded-full border border-surface-container-highest bg-surface-container-lowest px-3 py-1 text-[10px] font-black uppercase tracking-widest text-on-surface-variant">Created {formatRelative(agent.created_at)}</span>
                    </div>
                  </div>
                  <div className="absolute right-4 top-4 opacity-0 transition-opacity group-hover:opacity-100">
                    <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-surface-container-highest bg-surface-container-lowest shadow-sm">
                      <Settings className="h-4 w-4 text-brand-primary" />
                    </span>
                  </div>
                </div>
                <div className="p-5">
                  <p className="text-sm text-on-surface-variant leading-relaxed">Configure sources, tune behavior, and ship a crisp support experience.</p>
                  <div className="mt-5 flex items-center justify-between border-t border-surface-container-highest pt-4">
                    <span className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant opacity-60">Open agent</span>
                    <div className="p-2 -mr-2 text-brand-primary opacity-0 group-hover:opacity-100 group-hover:translate-x-1 transition-all"><ArrowRight className="w-4 h-4" /></div>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </div>
    </AppLayout>
  );
}
