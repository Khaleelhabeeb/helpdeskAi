import { HelpPageMiniPreview } from '../../components/deploy/HelpPageMiniPreview';
import { useDeploy } from './DeployProvider';

export default function HelpPageDeployPage() {
  const { displayName } = useDeploy();

  return (
    <div className="overflow-hidden rounded-2xl border border-surface-container-highest bg-surface-container-lowest shadow-sm">
      <div className="grid grid-cols-1 lg:grid-cols-2">
        <div className="space-y-6 border-b border-surface-container-highest p-6 lg:border-b-0 lg:border-r">
          <div>
            <h2 className="text-lg font-bold text-brand-primary">Help page settings</h2>
            <p className="mt-2 text-sm leading-relaxed text-on-surface-variant">
              A full-page help experience powered by your agent. Configuration and publishing will be available soon.
            </p>
          </div>
          <div className="rounded-xl border border-dashed border-amber-200 bg-amber-50 px-4 py-5 text-sm text-amber-900">
            <p className="font-bold">Coming soon</p>
            <p className="mt-2 leading-relaxed text-amber-800/90">
              You will be able to set a custom path, branding, and publish URL. For now, preview how the page will look.
            </p>
          </div>
        </div>
        <div className="relative min-h-[280px] bg-gradient-to-br from-amber-100 via-orange-50 to-yellow-100 p-8 lg:min-h-[360px]">
          <HelpPageMiniPreview name={displayName} />
        </div>
      </div>
    </div>
  );
}
