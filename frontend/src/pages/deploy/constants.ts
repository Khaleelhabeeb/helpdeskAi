import type { LucideIcon } from 'lucide-react';
import {
  FileText,
  LayoutGrid,
  Mail,
  MessageCircle,
  Phone,
  Smartphone,
} from 'lucide-react';

export type DeployChannelStatus = 'live' | 'preview' | 'soon';

export type DeployChannel = {
  id: string;
  path: string;
  label: string;
  description: string;
  icon: LucideIcon;
  status: DeployChannelStatus;
};

export const DEPLOY_CHANNELS: DeployChannel[] = [
  {
    id: 'overview',
    path: '',
    label: 'Overview',
    description: 'All deployment channels',
    icon: LayoutGrid,
    status: 'live',
  },
  {
    id: 'widget',
    path: 'widget',
    label: 'Chat widget',
    description: 'Floating chat on your site',
    icon: MessageCircle,
    status: 'live',
  },
  {
    id: 'help-page',
    path: 'help-page',
    label: 'Help page',
    description: 'Standalone /help experience',
    icon: FileText,
    status: 'preview',
  },
  {
    id: 'email',
    path: 'email',
    label: 'Email',
    description: 'Inbox automation',
    icon: Mail,
    status: 'soon',
  },
  {
    id: 'whatsapp',
    path: 'whatsapp',
    label: 'WhatsApp',
    description: 'Messaging channel',
    icon: Smartphone,
    status: 'soon',
  },
  {
    id: 'phone',
    path: 'phone',
    label: 'Phone',
    description: 'Voice support',
    icon: Phone,
    status: 'soon',
  },
];

export const COMING_SOON_CHANNELS = [
  {
    id: 'email',
    title: 'Email',
    copy: 'Connect your agent to an email address and let it respond to messages from your customers.',
    icon: Mail,
    iconBg: 'bg-[#EA4335]',
  },
  {
    id: 'whatsapp',
    title: 'WhatsApp',
    copy: 'Reply to WhatsApp conversations with the same trained support agent.',
    icon: Smartphone,
    iconBg: 'bg-[#25D366]',
  },
  {
    id: 'phone',
    title: 'Phone',
    copy: 'Let your AI agent handle inbound phone calls.',
    icon: Phone,
    iconBg: 'bg-[#7C3AED]',
    badge: 'Beta' as const,
  },
];

export const COMING_SOON_CHANNEL_IDS = new Set(COMING_SOON_CHANNELS.map((c) => c.id));
