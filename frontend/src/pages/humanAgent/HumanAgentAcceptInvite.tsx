import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { Loader2, Shield, Check, Lock, Mail, Send } from 'lucide-react';
import { API_BASE_URL, apiFetch } from '../../lib/api';
import { humanAgentStoreSession, PENDING_INVITE_TOKEN_KEY } from '../../lib/humanAgentApi';

export default function HumanAgentAcceptInvite() {
  const [params] = useSearchParams();
  const nav = useNavigate();
  const token = params.get('token') || '';
  const [emailHint, setEmailHint] = useState<string | null>(null);
  const [expired, setExpired] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [linkSent, setLinkSent] = useState(false);
  const [linkSending, setLinkSending] = useState(false);
  const [done, setDone] = useState(false);

  // Preferred path: one login for all — magic link signs the agent in, then the
  // invite is accepted automatically via verified email (no agent password).
  async function sendSignInLink() {
    if (!emailHint || linkSending) return;
    setError('');
    setLinkSending(true);
    try {
      await apiFetch('/auth/otp/request', {
        method: 'POST',
        auth: false,
        body: JSON.stringify({ email: emailHint }),
      });
      try { localStorage.setItem(PENDING_INVITE_TOKEN_KEY, token); } catch {}
      setLinkSent(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not send sign-in link');
    } finally {
      setLinkSending(false);
    }
  }

  useEffect(() => {
    if (!token) { setLoading(false); setError('Missing invite token. Open the link from your email.'); return; }
    let cancelled = false;
    async function check() {
      try {
        const res = await fetch(`${API_BASE_URL}/human-agent/auth/invite-status?token=${encodeURIComponent(token)}`);
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Invalid invite');
        if (cancelled) return;
        setEmailHint(data.email);
        if (data.name) setName(data.name);
        setExpired(!!data.expired);
        if (data.expired) setError('Invite link has expired. Ask the account owner to resend it.');
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Invalid invite token');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    check();
    return () => { cancelled = true; };
  }, [token]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    if (!password || password.length < 8) { setError('Password must be at least 8 characters'); return; }
    setSubmitting(true);
    try {
      const res = await fetch(`${API_BASE_URL}/human-agent/auth/accept-invite`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, password, name: name.trim() || undefined }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not accept invite');
      humanAgentStoreSession(data.access_token, data.human_agent);
      setDone(true);
      setTimeout(() => nav('/human-agent/dashboard', { replace: true }), 1200);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to accept invite');
    } finally {
      setSubmitting(false);
    }
  }

  if (done) {
    return (
      <div className="min-h-screen bg-[#f8f8f7] grid place-items-center p-6">
        <div className="w-full max-w-sm bg-white border border-zinc-200 rounded-2xl p-8 text-center">
          <div className="mx-auto w-12 h-12 rounded-full bg-emerald-100 text-emerald-600 grid place-items-center"><Check className="w-6 h-6" /></div>
          <h2 className="mt-4 font-bold text-zinc-900">You're all set!</h2>
          <p className="text-sm text-zinc-500 mt-1">Redirecting to your dashboard…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#f8f8f7] flex items-center justify-center p-6">
      <div className="w-full max-w-md bg-white border border-zinc-200 rounded-2xl p-8 shadow-sm">
        <div className="flex flex-col items-center mb-6">
          <div className="w-10 h-10 rounded-xl bg-black text-white grid place-items-center mb-3"><Shield className="w-5 h-5" /></div>
          <h1 className="text-xl font-bold tracking-tight text-zinc-900">Accept your invite</h1>
          <p className="text-sm text-zinc-500 text-center mt-1">{emailHint ? `Invite for ${emailHint}` : 'Set a password to activate your human agent account.'}</p>
        </div>

        {loading ? (
          <div className="py-10 flex items-center justify-center text-sm text-zinc-500"><Loader2 className="w-5 h-5 animate-spin mr-2" />Checking invite…</div>
        ) : (
          <>
            {error && <div className="mb-4 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>}
            {!expired && !error.includes('Missing') && (
              <div className="space-y-4">
                {linkSent ? (
                  <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
                    Sign-in link sent to <span className="font-mono font-bold">{emailHint}</span>. Click it in your email — your invite will be accepted automatically.
                  </div>
                ) : (
                  <button onClick={sendSignInLink} disabled={linkSending || !emailHint} className="w-full h-11 rounded-xl bg-black text-white text-sm font-bold hover:bg-zinc-800 disabled:opacity-50 flex items-center justify-center gap-2">
                    {linkSending ? <Loader2 className="w-4 h-4 animate-spin" /> : <><Send className="w-4 h-4" /> Email me a sign-in link</>}
                  </button>
                )}
                <div className="relative">
                  <div className="absolute inset-0 flex items-center"><span className="w-full border-t border-zinc-200" /></div>
                  <div className="relative flex justify-center text-[10px] uppercase font-bold tracking-widest"><span className="bg-white px-2 text-zinc-400">Or use a password (legacy)</span></div>
                </div>
                <form onSubmit={submit} className="space-y-4">
                  <div className="space-y-1.5">
                    <label className="text-xs font-bold uppercase tracking-widest text-zinc-500">Display name (optional)</label>
                    <div className="relative">
                      <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" />
                      <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Your name" className="w-full h-11 pl-10 pr-3 rounded-xl border border-zinc-200 bg-zinc-50 text-sm focus:bg-white focus:outline-none" />
                    </div>
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs font-bold uppercase tracking-widest text-zinc-500">Choose a password</label>
                    <div className="relative">
                      <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" />
                      <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="At least 8 characters" className="w-full h-11 pl-10 pr-3 rounded-xl border border-zinc-200 bg-zinc-50 text-sm focus:bg-white focus:outline-none" />
                    </div>
                  </div>
                  <button disabled={submitting || expired} className="w-full h-11 rounded-xl border border-zinc-200 bg-white text-zinc-800 text-sm font-bold hover:bg-zinc-50 disabled:opacity-50 flex items-center justify-center gap-2">
                    {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Activate with password'}
                  </button>
                </form>
              </div>
            )}
          </>
        )}

        <div className="mt-6 text-center text-xs text-zinc-500">
          Already activated? <Link to="/human-agent/login" className="font-bold text-black underline">Sign in</Link>
        </div>
      </div>
    </div>
  );
}
