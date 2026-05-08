import {
  User,
  MessageSquare,
  Slack,
  Smartphone,
  Globe,
  ChevronRight,
  Loader2,
  Save,
} from 'lucide-react';
import { AppLayout } from '../components/Layout';
import { cn } from '../lib/utils';
import { useEffect, useState } from 'react';
import { apiFetch, UserSettings } from '../lib/api';
import { useAuth } from '../lib/auth';

export default function Settings() {
  const { user } = useAuth();
  const [settings, setSettings] = useState<UserSettings | null>(null);
  const [isLoading, setLoading] = useState(true);
  const [isSaving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const channels = [
    { name: 'Slack', status: 'Coming Soon', icon: Slack, active: false, color: 'text-[#4A154B]' },
    { name: 'WhatsApp', status: 'Coming Soon', icon: Smartphone, active: false, color: 'text-[#25D366]' },
    { name: 'Web Widget', status: 'Available', icon: Globe, active: true, color: 'text-blue-500' },
  ];

  useEffect(() => {
    async function loadSettings() {
      setLoading(true);
      setError('');
      try {
        setSettings(await apiFetch<UserSettings>('/users/settings'));
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Could not load settings');
      } finally {
        setLoading(false);
      }
    }
    loadSettings();
  }, []);

  function updateSetting<K extends keyof UserSettings>(key: K, value: UserSettings[K]) {
    setSettings((current) => current ? { ...current, [key]: value } : current);
  }

  async function saveSettings() {
    if (!settings) return;
    setSaving(true);
    setError('');
    setNotice('');
    try {
      const payload = {
        widget_theme: settings.widget_theme,
        widget_color: settings.widget_color,
        widget_position: settings.widget_position,
        widget_size: settings.widget_size,
        email_notifications: settings.email_notifications,
        browser_notifications: settings.browser_notifications,
        notification_frequency: settings.notification_frequency,
        default_language: settings.default_language,
        response_style: settings.response_style,
        max_response_length: settings.max_response_length,
        auto_suggestions: settings.auto_suggestions,
        data_retention_days: settings.data_retention_days,
        analytics_enabled: settings.analytics_enabled,
        share_usage_data: settings.share_usage_data,
        api_rate_limit_preference: settings.api_rate_limit_preference,
        debug_mode: settings.debug_mode,
      };
      setSettings(await apiFetch<UserSettings>('/users/settings', { method: 'PUT', body: JSON.stringify(payload) }));
      setNotice('Settings saved.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save settings');
    } finally {
      setSaving(false);
    }
  }

  return (
    <AppLayout>
      <div className="space-y-12">
        <header>
          <h1 className="text-3xl font-bold tracking-tight text-brand-primary">Settings</h1>
          <p className="text-on-surface-variant mt-1 text-sm">Manage your account preferences and widget defaults.</p>
        </header>

        {(error || notice) && (
          <div className={cn('rounded-lg border px-4 py-3 text-sm font-medium', error ? 'border-rose-200 bg-rose-50 text-rose-700' : 'border-emerald-200 bg-emerald-50 text-emerald-700')}>
            {error || notice}
          </div>
        )}

        {isLoading ? (
          <div className="min-h-[260px] flex items-center justify-center text-on-surface-variant">
            <Loader2 className="w-5 h-5 animate-spin mr-2" />
            Loading settings...
          </div>
        ) : settings && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-12">
            <div className="lg:col-span-1 border-r border-surface-container-highest pr-12 hidden lg:block">
              <nav className="flex flex-col gap-1 sticky top-24">
                {['General Profile', 'Widget Defaults', 'Notifications', 'Integrations'].map((item, index) => (
                  <button key={item} className={cn(
                    'flex items-center justify-between px-4 py-3 rounded-lg text-sm transition-all',
                    index === 0 ? 'bg-brand-primary text-brand-on-primary font-bold' : 'text-on-surface-variant hover:text-brand-primary hover:bg-surface-container-low font-medium',
                  )}>
                    {item}
                    <ChevronRight className="w-4 h-4 opacity-40" />
                  </button>
                ))}
              </nav>
            </div>

            <div className="lg:col-span-2 space-y-12">
              <section className="bg-surface-container-lowest border border-surface-container-highest p-8 rounded-xl shadow-sm">
                <div className="flex flex-col gap-1 mb-8 pb-4 border-b border-surface-container-highest">
                  <h2 className="text-lg font-bold text-brand-primary flex items-center gap-2"><User className="w-5 h-5" /> General Profile</h2>
                  <p className="text-xs text-on-surface-variant uppercase font-bold tracking-widest">Authenticated through Supabase.</p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                  <div className="space-y-2">
                    <label className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant">Email Address</label>
                    <input
                      type="email"
                      value={user?.email ?? ''}
                      readOnly
                      className="w-full h-11 px-4 bg-surface-container-low border border-surface-container-highest rounded-lg text-sm text-on-surface-variant"
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant">Response Style</label>
                    <select
                      value={settings.response_style}
                      onChange={(event) => updateSetting('response_style', event.target.value)}
                      className="w-full h-11 px-4 bg-surface-container-low border border-surface-container-highest rounded-lg text-sm focus:outline-none focus:border-brand-primary transition-all focus:ring-1 focus:ring-brand-primary"
                    >
                      <option value="professional">Professional</option>
                      <option value="friendly">Friendly</option>
                      <option value="casual">Casual</option>
                    </select>
                  </div>
                </div>
              </section>

              <section className="bg-surface-container-lowest border border-surface-container-highest p-8 rounded-xl shadow-sm">
                <div className="flex flex-col gap-1 mb-8 pb-4 border-b border-surface-container-highest">
                  <h2 className="text-lg font-bold text-brand-primary flex items-center gap-2"><MessageSquare className="w-5 h-5" /> Widget Defaults</h2>
                  <p className="text-xs text-on-surface-variant font-bold uppercase tracking-widest">Used by the web chat widget and agent embeds.</p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                  <div className="space-y-2">
                    <label className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant">Theme</label>
                    <select value={settings.widget_theme} onChange={(event) => updateSetting('widget_theme', event.target.value)} className="w-full h-11 px-4 bg-surface-container-low border border-surface-container-highest rounded-lg text-sm focus:outline-none focus:border-brand-primary">
                      <option value="default">Default</option>
                      <option value="light">Light</option>
                      <option value="dark">Dark</option>
                    </select>
                  </div>
                  <div className="space-y-2">
                    <label className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant">Accent Color</label>
                    <div className="flex gap-3">
                      <input type="color" value={settings.widget_color} onChange={(event) => updateSetting('widget_color', event.target.value)} className="h-11 w-14 rounded-lg border border-surface-container-highest bg-surface-container-low" />
                      <input type="text" value={settings.widget_color} onChange={(event) => updateSetting('widget_color', event.target.value)} className="flex-1 h-11 px-4 bg-surface-container-low border border-surface-container-highest rounded-lg text-sm font-mono focus:outline-none focus:border-brand-primary" />
                    </div>
                  </div>
                  <div className="space-y-2">
                    <label className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant">Position</label>
                    <select value={settings.widget_position} onChange={(event) => updateSetting('widget_position', event.target.value)} className="w-full h-11 px-4 bg-surface-container-low border border-surface-container-highest rounded-lg text-sm focus:outline-none focus:border-brand-primary">
                      <option value="bottom-right">Bottom right</option>
                      <option value="bottom-left">Bottom left</option>
                      <option value="top-right">Top right</option>
                      <option value="top-left">Top left</option>
                    </select>
                  </div>
                  <div className="space-y-2">
                    <label className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant">Size</label>
                    <select value={settings.widget_size} onChange={(event) => updateSetting('widget_size', event.target.value)} className="w-full h-11 px-4 bg-surface-container-low border border-surface-container-highest rounded-lg text-sm focus:outline-none focus:border-brand-primary">
                      <option value="small">Small</option>
                      <option value="medium">Medium</option>
                      <option value="large">Large</option>
                    </select>
                  </div>
                </div>
              </section>

              <section className="bg-surface-container-lowest border border-surface-container-highest p-8 rounded-xl shadow-sm">
                <div className="flex flex-col gap-1 mb-8 pb-4 border-b border-surface-container-highest">
                  <h2 className="text-lg font-bold text-brand-primary">Notifications & Privacy</h2>
                  <p className="text-xs text-on-surface-variant font-bold uppercase tracking-widest">Tune operational preferences.</p>
                </div>
                <div className="grid gap-4">
                  {[
                    ['email_notifications', 'Email notifications'],
                    ['browser_notifications', 'Browser notifications'],
                    ['auto_suggestions', 'Auto suggestions'],
                    ['analytics_enabled', 'Analytics enabled'],
                    ['share_usage_data', 'Share usage data'],
                    ['debug_mode', 'Debug mode'],
                  ].map(([key, label]) => (
                    <label key={key} className="flex items-center justify-between p-4 border border-surface-container-highest rounded-lg bg-surface">
                      <span className="text-sm font-bold text-brand-primary">{label}</span>
                      <input
                        type="checkbox"
                        checked={Boolean(settings[key as keyof UserSettings])}
                        onChange={(event) => updateSetting(key as keyof UserSettings, event.target.checked as never)}
                        className="h-5 w-5 accent-brand-primary"
                      />
                    </label>
                  ))}
                </div>
              </section>

              <section className="bg-surface-container-lowest border border-surface-container-highest p-8 rounded-xl shadow-sm">
                <div className="flex flex-col gap-1 mb-8 pb-4 border-b border-surface-container-highest">
                  <h2 className="text-lg font-bold text-brand-primary">Connected Channels</h2>
                  <p className="text-xs text-on-surface-variant font-bold uppercase tracking-widest">Current deployment surfaces.</p>
                </div>

                <div className="space-y-4">
                  {channels.map((channel) => (
                    <div key={channel.name} className="flex items-center justify-between p-4 border border-surface-container-highest rounded-xl bg-surface group hover:border-brand-primary transition-all">
                      <div className="flex items-center gap-4">
                        <div className={cn('w-12 h-12 bg-surface-container-lowest border border-surface-container-highest rounded-lg flex items-center justify-center group-hover:bg-brand-primary group-hover:text-brand-on-primary transition-all shadow-sm', channel.color)}>
                          <channel.icon className="w-6 h-6" />
                        </div>
                        <div>
                          <div className="text-sm font-bold text-brand-primary">{channel.name}</div>
                          <div className="flex items-center gap-2 mt-0.5">
                            <span className={cn('w-1.5 h-1.5 rounded-full', channel.active ? 'bg-brand-primary' : 'bg-on-surface-variant opacity-20')} />
                            <span className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant">{channel.status}</span>
                          </div>
                        </div>
                      </div>
                      <button className={cn('text-[10px] font-black uppercase tracking-widest px-4 py-2 rounded-lg transition-all', channel.active ? 'bg-surface-container-highest text-brand-primary hover:bg-brand-primary hover:text-brand-on-primary' : 'bg-surface-container-high text-on-surface-variant')}>
                        {channel.active ? 'Configure' : 'Soon'}
                      </button>
                    </div>
                  ))}
                </div>
              </section>

              <div className="flex justify-end">
                <button onClick={saveSettings} disabled={isSaving} className="bg-brand-primary text-brand-on-primary text-[10px] font-black uppercase tracking-widest py-3 px-8 rounded-lg hover:opacity-90 transition-opacity flex items-center gap-2 disabled:opacity-50">
                  {isSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                  Save Changes
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  );
}
