import { Agent, API_BASE_URL } from '../../lib/api';

export type WidgetDeployment = {
  deployment_id: string;
  display_name: string;
  logo_url: string;
  initial_messages: string[];
  theme: 'light' | 'dark';
  primary_color: string;
  allowed_domains: string[];
  is_enabled: boolean;
  embed_script: string;
  help_page_enabled: boolean;
  help_page_slug: string;
  help_page_title: string;
  help_page_description: string;
  help_page_suggestions: string[];
};

export function defaultDeployment(agent?: Agent | null): WidgetDeployment {
  const displayName = agent?.name || 'Support Agent';
  return {
    deployment_id: '',
    display_name: displayName,
    logo_url: agent?.avatar_url || '',
    initial_messages: ['Hi! What can I help you with?'],
    theme: 'dark',
    primary_color: '#ffffff',
    allowed_domains: ['localhost', '127.0.0.1'],
    is_enabled: true,
    help_page_enabled: false,
    help_page_slug: '',
    help_page_title: '',
    help_page_description: '',
    help_page_suggestions: [],
    embed_script: `<script src="${API_BASE_URL}/static/widget.js" data-deployment-id="" defer></script>`,
  };
}
