import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { useParams } from 'react-router-dom';
import { Agent, apiFetch, API_BASE_URL } from '../../lib/api';
import { defaultDeployment, WidgetDeployment } from './types';

type DeployContextValue = {
  agentId: string | undefined;
  agent: Agent | null;
  deployment: WidgetDeployment;
  savedDeployment: WidgetDeployment | null;
  domains: string[];
  savedDomains: string[];
  isLoading: boolean;
  isSaving: boolean;
  error: string;
  notice: string;
  setError: (value: string) => void;
  setNotice: (value: string) => void;
  isDirty: boolean;
  displayName: string;
  previewGreeting: string;
  embedCode: string;
  logoImage: string | null;
  updateDeployment: (patch: Partial<WidgetDeployment>) => void;
  setDomains: React.Dispatch<React.SetStateAction<string[]>>;
  domainDraft: string;
  setDomainDraft: (value: string) => void;
  isAddingDomain: boolean;
  setIsAddingDomain: (value: boolean) => void;
  addDomain: () => void;
  removeDomain: (domain: string) => void;
  updateInitialMessage: (index: number, value: string) => void;
  removeInitialMessage: (index: number) => void;
  addInitialMessage: () => void;
  saveDeployment: () => Promise<void>;
  toggleWidgetEnabled: (enabled: boolean) => Promise<void>;
  regenerateDeploymentId: () => Promise<void>;
  uploadLogo: (file: File) => Promise<void>;
  setAgent: React.Dispatch<React.SetStateAction<Agent | null>>;
  isUploadingLogo: boolean;
};

const DeployContext = createContext<DeployContextValue | null>(null);

function normalizeDomain(value: string) {
  return value
    .trim()
    .toLowerCase()
    .replace(/^https?:\/\//, '')
    .replace(/\/.*$/, '')
    .replace(/^www\./, '');
}

export function DeployProvider({ children }: { children: ReactNode }) {
  const { agentId } = useParams();
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
  const [isUploadingLogo, setUploadingLogo] = useState(false);

  const isDirty = useMemo(() => {
    if (!savedDeployment) return false;
    return (
      JSON.stringify(deployment) !== JSON.stringify(savedDeployment) ||
      JSON.stringify(domains) !== JSON.stringify(savedDomains)
    );
  }, [deployment, domains, savedDeployment, savedDomains]);

  useEffect(() => {
    async function load() {
      if (!agentId) return;
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
        setError(err instanceof Error ? err.message : 'Could not load deploy data');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [agentId]);

  const embedCode = useMemo(() => {
    return `<script src="${API_BASE_URL}/static/widget-loader.js" data-deployment-id="${deployment.deployment_id}" defer></script>`;
  }, [deployment.deployment_id]);

  const previewGreeting =
    deployment.initial_messages.find((m) => m.trim())?.trim() ?? 'Hi! What can I help you with?';
  const displayName = deployment.display_name || agent?.name || 'Support Agent';
  const logoImage = deployment.logo_url || agent?.avatar_url || null;

  const updateDeployment = useCallback((patch: Partial<WidgetDeployment>) => {
    setDeployment((current) => ({ ...current, ...patch }));
    setNotice('');
  }, []);

  const updateInitialMessage = useCallback(
    (index: number, value: string) => {
      setDeployment((current) => ({
        ...current,
        initial_messages: current.initial_messages.map((message, idx) =>
          idx === index ? value : message
        ),
      }));
      setNotice('');
    },
    []
  );

  const removeInitialMessage = useCallback((index: number) => {
    setDeployment((current) => {
      const next = current.initial_messages.filter((_, idx) => idx !== index);
      return { ...current, initial_messages: next.length ? next : [''] };
    });
    setNotice('');
  }, []);

  const addInitialMessage = useCallback(() => {
    setDeployment((current) => ({
      ...current,
      initial_messages: [...current.initial_messages, ''],
    }));
    setNotice('');
  }, []);

  const addDomain = useCallback(() => {
    const normalized = normalizeDomain(domainDraft);
    if (!normalized) return;
    setDomains((current) => (current.includes(normalized) ? current : [...current, normalized]));
    setDomainDraft('');
    setIsAddingDomain(false);
    setNotice('');
  }, [domainDraft]);

  const removeDomain = useCallback((domain: string) => {
    setDomains((current) => current.filter((item) => item !== domain));
    setNotice('');
  }, []);

  const saveDeployment = useCallback(async () => {
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
      const nextDomains = updated.allowed_domains?.length ? updated.allowed_domains : domains;
      setDomains(nextDomains);
      setSavedDomains(nextDomains);
      setNotice('Widget deployment saved.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save widget deployment');
    } finally {
      setSaving(false);
    }
  }, [agent, deployment, domains]);

  const toggleWidgetEnabled = useCallback(
    async (enabled: boolean) => {
      if (!agent) return;
      const previous = deployment.is_enabled;
      updateDeployment({ is_enabled: enabled });
      try {
        const updated = await apiFetch<WidgetDeployment>(`/agents/${agent.id}/widget-deployment`, {
          method: 'PATCH',
          body: JSON.stringify({ is_enabled: enabled }),
        });
        setDeployment(updated);
        setSavedDeployment(updated);
      } catch (err) {
        updateDeployment({ is_enabled: previous });
        setError(err instanceof Error ? err.message : 'Could not update widget status');
      }
    },
    [agent, deployment.is_enabled, updateDeployment]
  );

  const regenerateDeploymentId = useCallback(async () => {
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
      const nextDomains = updated.allowed_domains?.length ? updated.allowed_domains : domains;
      setDomains(nextDomains);
      setSavedDomains(nextDomains);
      setNotice('Embed key regenerated. Replace the old snippet on any websites using this widget.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not regenerate deployment key');
    } finally {
      setSaving(false);
    }
  }, [agent, domains]);

  const uploadLogo = useCallback(
    async (file: File) => {
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
    },
    [agent, updateDeployment]
  );

  const value = useMemo<DeployContextValue>(
    () => ({
      agentId,
      agent,
      deployment,
      savedDeployment,
      domains,
      savedDomains,
      isLoading,
      isSaving,
      error,
      notice,
      setError,
      setNotice,
      isDirty,
      displayName,
      previewGreeting,
      embedCode,
      logoImage,
      updateDeployment,
      setDomains,
      domainDraft,
      setDomainDraft,
      isAddingDomain,
      setIsAddingDomain,
      addDomain,
      removeDomain,
      updateInitialMessage,
      removeInitialMessage,
      addInitialMessage,
      saveDeployment,
      toggleWidgetEnabled,
      regenerateDeploymentId,
      uploadLogo,
      setAgent,
      isUploadingLogo,
    }),
    [
      agentId,
      agent,
      deployment,
      savedDeployment,
      domains,
      savedDomains,
      isLoading,
      isSaving,
      error,
      notice,
      isDirty,
      displayName,
      previewGreeting,
      embedCode,
      logoImage,
      updateDeployment,
      domainDraft,
      isAddingDomain,
      addDomain,
      removeDomain,
      updateInitialMessage,
      removeInitialMessage,
      addInitialMessage,
      saveDeployment,
      toggleWidgetEnabled,
      regenerateDeploymentId,
      uploadLogo,
      isUploadingLogo,
    ]
  );

  return <DeployContext.Provider value={value}>{children}</DeployContext.Provider>;
}

export function useDeploy() {
  const context = useContext(DeployContext);
  if (!context) throw new Error('useDeploy must be used within DeployProvider');
  return context;
}
