import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { motion } from 'motion/react';
import { ArrowRight } from 'lucide-react';
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
  const [password, setPassword] = useState('');
  const [mode, setMode] = useState<'signin' | 'signup'>('signin');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [isSubmitting, setSubmitting] = useState(false);
  const [isGoogleLoading, setGoogleLoading] = useState(false);
  const navigate = useNavigate();
  const { signIn, signUp } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setNotice('');
    setSubmitting(true);
    try {
      if (mode === 'signin') {
        await signIn(email, password);
      } else {
        await signUp(email, password);
      }
      navigate('/dashboard');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Authentication failed';
      if (message.toLowerCase().includes('confirm your email')) {
        setNotice(message);
      } else {
        setError(message);
      }
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
          <p className="text-sm text-on-surface-variant">{mode === 'signin' ? 'Sign in to your account' : 'Create your workspace'}</p>
        </div>

        <div className="space-y-4 mb-8">
          <button 
            onClick={handleGoogleLogin}
            disabled={isGoogleLoading}
            className="w-full flex items-center justify-center gap-3 bg-surface border border-surface-container-highest h-11 rounded-lg text-sm font-bold text-brand-primary hover:bg-surface-container-low transition-all disabled:cursor-not-allowed disabled:opacity-70"
          >
            <img src="https://www.google.com/favicon.ico" alt="Google" className="w-4 h-4" />
            {isGoogleLoading ? 'Connecting...' : 'Sign in with Google'}
          </button>
          
          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t border-surface-container-highest"></span>
            </div>
            <div className="relative flex justify-center text-[10px] uppercase font-bold tracking-widest leading-none">
              <span className="bg-surface-container-lowest px-2 text-on-surface-variant opacity-40">Or continue with</span>
            </div>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {(error || notice) && (
            <div className={error ? "rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-medium text-rose-700" : "rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-700"}>
              {error || notice}
            </div>
          )}
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-wider text-on-surface-variant" htmlFor="email">
              Email
            </label>
            <input 
              type="email" 
              id="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
              className="w-full h-11 bg-surface-container-low border border-surface-container-highest rounded-lg px-4 text-sm focus:outline-none focus:border-brand-primary focus:ring-1 focus:ring-brand-primary transition-all placeholder:text-on-surface-variant/30"
            />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold uppercase tracking-wider text-on-surface-variant" htmlFor="password">
                Password
              </label>
              <a href="#" className="text-xs text-on-surface-variant hover:text-brand-primary transition-colors">Forgot?</a>
            </div>
            <input 
              type="password" 
              id="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              className="w-full h-11 bg-surface-container-low border border-surface-container-highest rounded-lg px-4 text-sm focus:outline-none focus:border-brand-primary focus:ring-1 focus:ring-brand-primary transition-all placeholder:text-on-surface-variant/30"
            />
          </div>

          <button 
            type="submit"
            disabled={isSubmitting}
            className="w-full bg-brand-primary text-brand-on-primary font-medium h-11 rounded-lg hover:opacity-90 transition-all flex items-center justify-center gap-2 group"
          >
            {isSubmitting ? 'Please wait...' : mode === 'signin' ? 'Sign In' : 'Create Account'}
            <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
          </button>
        </form>

        <div className="mt-8 pt-8 border-t border-surface-container-highest flex justify-center">
          <p className="text-sm text-on-surface-variant">
            {mode === 'signin' ? "Don't have an account?" : 'Already have an account?'} 
            <button
              type="button"
              onClick={() => {
                setMode(mode === 'signin' ? 'signup' : 'signin');
                setError('');
                setNotice('');
              }}
              className="text-brand-primary hover:underline font-bold ml-1"
            >
              {mode === 'signin' ? 'Sign Up' : 'Sign In'}
            </button>
          </p>
        </div>
      </motion.div>
    </div>
  );
}
