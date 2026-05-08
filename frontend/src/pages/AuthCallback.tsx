import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { useAuth } from '../lib/auth';

const OAUTH_VERIFIER_KEY = 'helpdeskai.oauth_code_verifier';

function readParams() {
  const hash = new URLSearchParams(window.location.hash.replace(/^#/, ''));
  const query = new URLSearchParams(window.location.search);
  return {
    accessToken: hash.get('access_token') || query.get('access_token'),
    refreshToken: hash.get('refresh_token') || query.get('refresh_token'),
    error: hash.get('error_description') || query.get('error_description') || hash.get('error') || query.get('error'),
    code: query.get('code'),
  };
}

export default function AuthCallback() {
  const navigate = useNavigate();
  const { completeOAuthSignIn, exchangeOAuthCode } = useAuth();
  const [message, setMessage] = useState('Finishing Google sign-in...');
  const [failed, setFailed] = useState(false);
  const handledRef = useRef(false);

  useEffect(() => {
    if (handledRef.current) return;
    handledRef.current = true;

    const params = readParams();
    if (params.error) {
      setFailed(true);
      setMessage(params.error === 'Not authenticated' ? 'Google did not return a usable session. Please try signing in again.' : params.error);
      return;
    }

    if (!params.accessToken) {
      if (params.code) {
        const verifier = sessionStorage.getItem(OAUTH_VERIFIER_KEY);
        if (!verifier) {
          setFailed(true);
          setMessage('Google sign-in session expired. Please try again.');
          return;
        }
        setMessage('Finishing secure Google sign-in...');
        exchangeOAuthCode(params.code, verifier, `${window.location.origin}/auth/callback`)
          .then(() => {
            sessionStorage.removeItem(OAUTH_VERIFIER_KEY);
            navigate('/dashboard', { replace: true });
          })
          .catch((err) => {
            setFailed(true);
            setMessage(err instanceof Error ? err.message : 'Could not finish Google sign-in.');
          });
        return;
      }

      setFailed(true);
      setMessage('Google sign-in did not return an access token.');
      return;
    }

    completeOAuthSignIn(params.accessToken, params.refreshToken)
      .then(() => navigate('/dashboard', { replace: true }))
      .catch((err) => {
        setFailed(true);
        setMessage(err instanceof Error ? err.message : 'Could not finish Google sign-in.');
      });
  }, [completeOAuthSignIn, exchangeOAuthCode, navigate]);

  return (
    <div className="min-h-screen bg-surface flex items-center justify-center p-6">
      <div className="w-full max-w-sm bg-surface-container-lowest border border-surface-container-highest rounded-xl p-8 text-center shadow-sm">
        {!failed && <Loader2 className="w-6 h-6 animate-spin mx-auto mb-4 text-brand-primary" />}
        <h1 className="text-xl font-bold text-brand-primary">{failed ? 'Google sign-in needs attention' : 'Signing you in'}</h1>
        <p className="mt-3 text-sm text-on-surface-variant">{message}</p>
        {failed && (
          <Link to="/login" className="mt-6 inline-flex h-10 items-center justify-center rounded-lg bg-brand-primary px-5 text-sm font-bold text-brand-on-primary">
            Back to login
          </Link>
        )}
      </div>
    </div>
  );
}
