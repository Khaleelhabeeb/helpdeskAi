import React, { useEffect, useState } from 'react';
import { motion } from 'motion/react';
import { ArrowRight, Mail, Loader2, CheckCircle2, Send } from 'lucide-react';
import { Logo } from '../components/Logo';
import { useAuth } from '../lib/auth';
import { apiFetch } from '../lib/api';

const OAUTH_VERIFIER_KEY = 'helpdeskai.oauth_code_verifier';

function base64UrlEncode(bytes: Uint8Array) {
  let binary = '';
  bytes.forEach((byte) => {
    binary += String.fromCharCode(byte);
  });
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

async function createPkcePair() {
  const random = new Uint8Array(32);
  crypto.getRandomValues(random);
  const verifier = base64UrlEncode(random);
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier));
  return {
    verifier,
    challenge: base64UrlEncode(new Uint8Array(digest)),
  };
}

export default function Login() {
  const [email, setEmail] = useState('');
  const [isSent, setIsSent] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [isSubmitting, setSubmitting] = useState(false);
  const [isGoogleLoading, setGoogleLoading] = useState(false);
  const [resendCooldown, setResendCooldown] = useState(0);
  const { requestOtp } = useAuth();

  // Resend cooldown tick
  useEffect(() => {
    if (resendCooldown <= 0) return;
    const id = window.setTimeout(() => setResendCooldown((c) => c - 1), 1000);
    return () => window.clearTimeout(id);
  }, [resendCooldown]);

  const handleSendLink = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setNotice('');
    if (!email.trim()) {
      setError('Please enter your email address.');
      return;
    }
    setSubmitting(true);
    try {
      await requestOtp(email.trim());
      setIsSent(true);
      setNotice(`Magic link sent to ${email.trim()}. Open your email and click the link to sign in — it expires in a few minutes.`);
      setResendCooldown(60);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Could not send email. Please try again.';
      setError(message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleResend = async () => {
    if (resendCooldown > 0) return;
    setError('');
    setNotice('');
    setSubmitting(true);
    try {
      await requestOtp(email.trim());
      setNotice(`We resent the magic link to ${email.trim()}. Check spam if you don't see it.`);
      setResendCooldown(60);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not resend. Try again in a minute.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleGoogleLogin = async () => {
    setError('');
    setNotice('');
    setGoogleLoading(true);
    try {
      const config = await apiFetch<{ url: string; anon_key: string }>('/auth/supabase-config', { auth: false });
      const redirectTo = `${window.location.origin}/auth/callback`;
      const pkce = await createPkcePair();
      sessionStorage.setItem(OAUTH_VERIFIER_KEY, pkce.verifier);
      const authorizeUrl = new URL(`${config.url}/auth/v1/authorize`);
      authorizeUrl.searchParams.set('provider', 'google');
      authorizeUrl.searchParams.set('redirect_to', redirectTo);
      authorizeUrl.searchParams.set('code_challenge', pkce.challenge);
      authorizeUrl.searchParams.set('code_challenge_method', 'S256');
      window.location.assign(authorizeUrl.toString());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not start Google sign-in.');
      setGoogleLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-surface flex items-center justify-center p-6 selection:bg-brand-primary selection:text-brand-on-primary font-sans">
      <motion.div 
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="w-full max-w-sm bg-surface-container-lowest border border-surface-container-highest rounded-xl p-8 shadow-sm"
      >
        <div className="flex flex-col items-center mb-8">
          <Logo className="mb-4" />
          <p className="text-sm text-on-surface-variant text-center">
            {isSent ? 'Check your email' : 'Sign in or create account with a magic link'}
          </p>
        </div>

        <div className="space-y-4 mb-8">
          <button 
            onClick={handleGoogleLogin}
            disabled={isGoogleLoading || isSubmitting}
            className="w-full flex items-center justify-center gap-3 bg-surface border border-surface-container-highest h-11 rounded-lg text-sm font-bold text-brand-primary hover:bg-surface-container-low transition-all disabled:cursor-not-allowed disabled:opacity-70"
          >
            <img src="https://www.google.com/favicon.ico" alt="Google" className="w-4 h-4" />
            {isGoogleLoading ? 'Connecting...' : 'Continue with Google'}
          </button>
          
          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t border-surface-container-highest"></span>
            </div>
            <div className="relative flex justify-center text-[10px] uppercase font-bold tracking-widest leading-none">
              <span className="bg-surface-container-lowest px-2 text-on-surface-variant opacity-40">Or continue with email</span>
            </div>
          </div>
        </div>

        {(error || notice) && (
          <div className={error ? "mb-6 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-medium text-rose-700" : "mb-6 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-700 flex gap-3"}>
            {!error && <CheckCircle2 className="w-5 h-5 shrink-0 mt-0.5" />}
            <span>{error || notice}</span>
          </div>
        )}

        {!isSent ? (
          <form onSubmit={handleSendLink} className="space-y-6">
            <div className="space-y-2">
              <label className="text-xs font-semibold uppercase tracking-wider text-on-surface-variant" htmlFor="email">
                Email address
              </label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-on-surface-variant/50" />
                <input 
                  type="email" 
                  id="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  required
                  autoFocus
                  autoComplete="email"
                  className="w-full h-11 bg-surface-container-low border border-surface-container-highest rounded-lg pl-10 pr-4 text-sm focus:outline-none focus:border-brand-primary focus:ring-1 focus:ring-brand-primary transition-all placeholder:text-on-surface-variant/30"
                />
              </div>
              <p className="text-[11px] text-on-surface-variant/70">
                We&apos;ll email you a magic link. Click it to sign in — no password needed.
              </p>
            </div>

            <button 
              type="submit"
              disabled={isSubmitting || isGoogleLoading}
              className="w-full bg-brand-primary text-brand-on-primary font-medium h-11 rounded-lg hover:opacity-90 transition-all flex items-center justify-center gap-2 group disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {isSubmitting ? <><Loader2 className="w-4 h-4 animate-spin" /> Sending link...</> : <><Send className="w-4 h-4" /> Send magic link <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" /></>}
            </button>
          </form>
        ) : (
          <div className="space-y-6">
            <div className="rounded-xl bg-surface-container-low border border-surface-container-highest p-5 text-center">
              <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-emerald-100 text-emerald-600">
                <Mail className="w-5 h-5" />
              </div>
              <p className="text-sm font-semibold text-on-surface">Magic link sent to</p>
              <p className="mt-1 text-sm font-mono font-medium text-brand-primary break-all">{email}</p>
              <p className="mt-3 text-xs leading-relaxed text-on-surface-variant">
                Open your inbox and click the link to sign in. The link expires in a few minutes and can only be used once. You can close this tab — the email will open a new one.
              </p>
            </div>

            <div className="flex flex-col gap-3">
              <button
                type="button"
                onClick={handleResend}
                disabled={resendCooldown > 0 || isSubmitting}
                className="w-full h-11 rounded-lg border border-surface-container-highest bg-surface font-medium text-sm hover:bg-surface-container-low transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {isSubmitting ? <><Loader2 className="w-4 h-4 animate-spin" /> Resending...</> : resendCooldown > 0 ? `Resend link in ${resendCooldown}s` : 'Resend magic link'}
              </button>
              <button
                type="button"
                onClick={() => {
                  setIsSent(false);
                  setError('');
                  setNotice('');
                  setResendCooldown(0);
                }}
                className="text-sm text-on-surface-variant hover:text-brand-primary transition-colors text-center"
              >
                Use a different email
              </button>
            </div>
          </div>
        )}

        <div className="mt-8 pt-6 border-t border-surface-container-highest">
          <p className="text-[11px] leading-relaxed text-on-surface-variant/60 text-center">
            Magic links expire after a few minutes and can only be used once. If you don&apos;t see the email, check spam.
          </p>
          <p className="mt-2 text-[11px] leading-relaxed text-on-surface-variant/60 text-center">
            Support agent with a team invite? Sign in here with your invited email — you&apos;ll land in your agent workspace automatically.
          </p>
        </div>
      </motion.div>
    </div>
  );
}
