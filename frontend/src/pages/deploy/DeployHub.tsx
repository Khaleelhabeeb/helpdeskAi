import { useParams } from 'react-router-dom';
import { ChannelCard } from '../../components/deploy/ChannelCard';
import { ChatWidgetMiniPreview } from '../../components/deploy/ChatWidgetMiniPreview';
import { ComingSoonCard } from '../../components/deploy/ComingSoonCard';
import { HelpPageMiniPreview } from '../../components/deploy/HelpPageMiniPreview';
import { COMING_SOON_CHANNELS } from './constants';
import { useDeploy } from './DeployProvider';

export default function DeployHub() {
  const { agentId } = useParams();
  const base = `/agents/${agentId}/deploy`;
  const {
    agent,
    deployment,
    displayName,
    previewGreeting,
    toggleWidgetEnabled,
  } = useDeploy();

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ChannelCard
          title="Chat widget"
          description="Add a floating chat window to your site."
          previewGradient="bg-gradient-to-br from-sky-100 via-sky-50 to-indigo-100"
          preview={
            <ChatWidgetMiniPreview
              name={displayName}
              logoUrl={deployment.logo_url || agent?.avatar_url}
              greeting={previewGreeting}
              theme={deployment.theme}
              primaryColor={deployment.primary_color}
            />
          }
          enabled={deployment.is_enabled}
          onToggle={toggleWidgetEnabled}
          manageTo={`${base}/widget`}
          showMobileButton
        />

        <ChannelCard
          title="Help page"
          description="ChatGPT-style help page, deployed standalone or under a path on your site (/help)."
          previewGradient="bg-gradient-to-br from-amber-100 via-orange-50 to-yellow-100"
          preview={<HelpPageMiniPreview name={displayName} />}
          enabled={false}
          toggleDisabled
          manageTo={`${base}/help-page`}
          manageLabel="Manage"
        />
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {COMING_SOON_CHANNELS.map((channel) => (
          <ComingSoonCard
            key={channel.id}
            title={channel.title}
            copy={channel.copy}
            icon={channel.icon}
            iconBg={channel.iconBg}
            badge={channel.badge}
            detailTo={`${base}/${channel.id}`}
          />
        ))}
      </div>
    </div>
  );
}
