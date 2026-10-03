import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowRight, Building2, Headset, Loader2 } from 'lucide-react';
import { ProtectedRoute, readSessionRoles, fetchSessionRoles } from '../lib/auth';
import { HUMAN_AGENT_SELECTION_KEY } from '../lib/humanAgentApi';
import { Logo } from '../components/Logo';
import type { SessionRoles } from '../lib/auth';

function Picker() {
  const nav = useNavigate();
  const [roles, setRoles] = useState<SessionRoles | null>(() => readSessionRoles());
  const [loading, setLoading] = useState(!roles);

  useEffect(() => {
    let cancelled = false;
    if (!roles) {
      fetchSessionRoles()
        .then((next) => { if (!cancelled) { setRoles(next); setLoading(false); } })
        .catch(() => { if (!cancelled) setLoading(false); });
    }
    return () => { cancelled = true; };
  }, [roles]);

  const memberships = (roles?.memberships || []).filter((m) => m.status === 'active');
  const ownsAgents = (roles?.owned_agents || []).length > 0;

  useEffect(() => {
    if (!loading && roles && memberships.length === 0 && !ownsAgents) nav('/dashboard', { replace: true });
    else if (!loading && roles && memberships.length > 0 && !ownsAgents) nav('/human-agent/dashboard', { replace: true });
  }, [loading, roles, memberships.length, ownsAgents, nav]);

  function chooseAgent(id: string) {
    try { localStorage.setItem(HUMAN_AGENT_SELECTION_KEY, id); } catch {}
    nav('/human-agent/dashboard', { replace: true });
  }

  function chooseOwner() {
    try { localStorage.removeItem(HUMAN_AGENT_SELECTION_KEY); } catch {}
    nav('/dashboard', { replace: true });
  }

  return (
    <div className="min-h-screen bg-surface flex items-center justify-center p-6">
      <div className="w-full max-w-md bg-surface-container-lowest border border-surface-container-highest rounded-2xl p-8 shadow-sm">
        <div className="flex flex-col items-center mb-6">
          <Logo className="mb-3" />
          <h1 className="text-xl font-bold text-brand-primary">Choose your workspace</h1>
          <p className="text-sm text-on-surface-variant mt-1">One sign-in, every role. Pick where to go.</p>
        </div>
        {loading ? (
          <div className="py-8 flex items-center justify-center text-sm text-on-surface-variant">
            <Loader2 className="w-5 h-5 animate-spin mr-2" />Loading workspaces…
          </div>
        ) : (
          <div className="space-y-3">
            {ownsAgents && (
              <button onClick={chooseOwner} className="w-full flex items-center gap-3 rounded-xl border border-surface-container-highest bg-surface-container-low p-4 text-left hover:border-brand-primary/40 transition-all">
                <span className="w-10 h-10 rounded-xl bg-brand-primary/10 text-brand-primary grid place-items-center"><Building2 className="w-5 h-5" /></span>
                <span className="flex-1">
                  <span className="block text-sm font-bold text-brand-primary">Owner workspace</span>
                  <span className="block text-xs text-on-surface-variant">Manage agents, knowledge & team</span>
                </span>
                <ArrowRight className="w-4 h-4 text-on-surface-variant" />
              </button>
            )}
            {memberships.map((m) => (
              <button key={m.human_agent_id} onClick={() => chooseAgent(m.human_agent_id)} className="w-full flex items-center gap-3 rounded-xl border border-surface-container-highest bg-surface-container-low p-4 text-left hover:border-brand-primary/40 transition-all">
                <span className="w-10 h-10 rounded-xl bg-black text-white grid place-items-center"><Headset className="w-5 h-5" /></span>
                <span className="flex-1">
                  <span className="block text-sm font-bold text-brand-primary">Support agent{m.owner_email ? ` · ${m.owner_email}` : ''}</span>
                  <span className="block text-xs text-on-surface-variant">{m.agent_ids.length} assigned AI agent{m.agent_ids.length === 1 ? '' : 's'}</span>
                </span>
                <ArrowRight className="w-4 h-4 text-on-surface-variant" />
              </button>
            ))}
          </div>
        )}
        <div className="mt-6 text-center text-xs text-on-surface-variant">
          <Link to="/login" className="underline hover:text-brand-primary">Use a different email</Link>
        </div>
      </div>
    </div>
  );
}

export default function Welcome() {
  return <ProtectedRoute><Picker /></ProtectedRoute>;
}
