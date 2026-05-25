import { Loader2, Save } from 'lucide-react';
import { useDeploy } from './DeployProvider';

export function WidgetDeployActions() {
  const { isDirty, isSaving, saveDeployment } = useDeploy();

  return (
    <div className="flex items-center gap-2">
      {isDirty && (
        <span className="hidden text-[10px] font-bold uppercase tracking-widest text-amber-600 sm:inline">
          Unsaved
        </span>
      )}
      <button
        type="button"
        onClick={saveDeployment}
        disabled={isSaving || !isDirty}
        className="inline-flex h-9 items-center justify-center gap-1.5 rounded-lg bg-brand-primary px-3.5 text-xs font-bold text-brand-on-primary disabled:opacity-50"
      >
        {isSaving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
        Save
      </button>
    </div>
  );
}
