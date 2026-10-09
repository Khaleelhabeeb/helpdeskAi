import { useEffect, useMemo, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { API_BASE_URL, apiFetch } from '../lib/api';

type HelpPageConfig = {
  deployment_id: string;
  display_name: string;
  logo_url: string;
  theme: 'light' | 'dark';
  primary_color: string;
  title: string;
  description: string;
  suggestions: string[];
};

const VISITOR_KEY = 'helpdeskai.help_visitor_id';

function visitorId() {
  try {
    let id = localStorage.getItem(VISITOR_KEY);
    if (!id) {
      id = crypto.randomUUID();
      localStorage.setItem(VISITOR_KEY, id);
    }
    return id;
  } catch {
    return crypto.randomUUID();
  }
}

export default function HelpCenter() {
  const { slug = '' } = useParams();
  const [config, setConfig] = useState<HelpPageConfig | null>(null);
  const [status, setStatus] = useState<'loading' | 'ready' | 'missing'>('loading');
  const iframeRef = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    let cancelled = false;
    apiFetch<HelpPageConfig>(`/public/help/${encodeURIComponent(slug)}`, { auth: false })
      .then((data) => {
        if (cancelled) return;
        setConfig(data);
        setStatus('ready');
        document.title = `${data.display_name} — Help`;
      })
      .catch(() => !cancelled && setStatus('missing'));
    return () => {
      cancelled = true;
    };
  }, [slug]);

  // The panel asks for branding via WIDGET_READY, same handshake as the embed loader
  useEffect(() => {
    if (!config) return;
    const apiOrigin = new URL(API_BASE_URL).origin;
    function onMessage(event: MessageEvent) {
      if (event.origin !== apiOrigin || event.source !== iframeRef.current?.contentWindow) return;
      if (event.data?.type === 'WIDGET_READY') {
        iframeRef.current?.contentWindow?.postMessage(
          {
            type: 'WIDGET_CONFIG',
            config: {
              display_name: config!.display_name,
              logo_url: config!.logo_url,
              initial_messages: [config!.description ? `${config!.title}\n${config!.description}` : config!.title],
              suggestions: config!.suggestions,
              theme: config!.theme,
              primary_color: config!.primary_color,
            },
          },
          apiOrigin
        );
      }
    }
    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, [config]);

  const panelSrc = useMemo(() => {
    if (!config) return '';
    const params = new URLSearchParams({
      deployment_id: config.deployment_id,
      api_base: API_BASE_URL,
      visitor_id: visitorId(),
      mode: 'page',
    });
    return `${API_BASE_URL}/static/widget-panel.html?${params.toString()}`;
  }, [config]);

  if (status === 'loading') {
    return (
      <div className="grid min-h-screen place-items-center bg-white">
        <Loader2 className="h-5 w-5 animate-spin text-zinc-400" />
      </div>
    );
  }

  if (status === 'missing' || !config) {
    return (
      <div className="grid min-h-screen place-items-center bg-white px-6 text-center">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-950">This help page isn't available</h1>
          <p className="mt-2 text-sm text-zinc-500">The link may be wrong, or the page has been turned off.</p>
        </div>
      </div>
    );
  }

  // The whole page is the chat panel — same UI as the widget, full-bleed
  return (
    <iframe
      ref={iframeRef}
      src={panelSrc}
      title={`${config.display_name} help`}
      sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
      allow="clipboard-write"
      className="block h-[100dvh] w-full border-0"
    />
  );
}
