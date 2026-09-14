import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Loader2, Mail, Lock, ArrowRight, Shield } from 'lucide-react';
import { API_BASE_URL } from '../../lib/api';
import { humanAgentStoreSession } from '../../lib/humanAgentApi';

export default function HumanAgentLogin() {
  const nav = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(''); setNotice('');
    if (!email.trim() || !password) { setError('Email and password are required'); return; }
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/human-agent/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim(), password }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Login failed');
      humanAgentStoreSession(data.access_token, data.human_agent);
      setNotice('Signed in — redirecting…');
      setTimeout(() => nav('/human-agent/dashboard', { replace: true }), 400);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#f8f8f7] flex items-center justify-center p-6">
      <div className="w-full max-w-sm bg-white border border-zinc-200 rounded-2xl p-8 shadow-sm">
        <div className="flex flex-col items-center mb-8">
          <div className="w-10 h-10 rounded-xl bg-black text-white grid place-items-center mb-3"><Shield className="w-5 h-5" /></div>
          <h1 className="text-xl font-bold tracking-tight text-zinc-900">Human agent sign in</h1>
          <p className="text-sm text-zinc-500 text-center mt-1">Separate from the owner account. Ask your owner for an invite if you don't have one.</p>
        </div>

        {(error || notice) && (
          <div className={`mb-5 rounded-xl border px-4 py-3 text-sm ${error ? 'border-rose-200 bg-rose-50 text-rose-700' : 'border-emerald-200 bg-emerald-50 text-emerald-700'}`}>{error || notice}</div>
        )}

        <form onSubmit={onSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-bold uppercase tracking-widest text-zinc-500">Email</label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" />
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com" className="w-full h-11 pl-10 pr-3 rounded-xl border border-zinc-200 bg-zinc-50 text-sm focus:bg-white focus:border-zinc-300 focus:outline-none" />
            </div>
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-bold uppercase tracking-widest text-zinc-500">Password</label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" />
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" className="w-full h-11 pl-10 pr-3 rounded-xl border border-zinc-200 bg-zinc-50 text-sm focus:bg-white focus:border-zinc-300 focus:outline-none" />
            </div>
          </div>
          <button disabled={loading} className="w-full h-11 rounded-xl bg-black text-white text-sm font-bold hover:bg-zinc-800 disabled:opacity-50 flex items-center justify-center gap-2">
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <><span>Sign in</span><ArrowRight className="w-4 h-4" /></>}
          </button>
        </form>

        <div className="mt-6 text-center text-xs text-zinc-500">
          Invite link? <Link to="/human-agent/accept-invite" className="font-bold text-black underline">Accept invite</Link> · <Link to="/login" className="font-bold text-black underline">Owner login</Link>
        </div>
      </div>
    </div>
  );
}
