import { ReactNode, useState } from 'react';
import { Link } from 'react-router-dom';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { PlayCircle, Compass } from 'lucide-react';
import { useLanguage } from '@/contexts/LanguageContext';
import { useAuth } from '@/contexts/AuthContext';
import api from '@/services/api';
import { trackUsage } from '@/hooks/useUsageTracking';

interface EmptyStateProps {
  icon: ReactNode;
  title: string;
  hint: string;
  primaryAction?: ReactNode;
  /** If true, show the "Load realistic sample data" CTA (for admin / compliance officer). */
  showLoadSamples?: boolean;
  /** On-success callback (e.g. refresh list). */
  onSamplesLoaded?: () => void;
}

export function EmptyState({
  icon,
  title,
  hint,
  primaryAction,
  showLoadSamples = false,
  onSamplesLoaded,
}: EmptyStateProps) {
  const { t, language } = useLanguage();
  const { user } = useAuth();
  const isAr = language === 'ar';
  const canSeed = user?.role === 'admin' || user?.role === 'compliance_officer';
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleLoad = async () => {
    setLoading(true);
    setResult(null);
    setError(null);
    try {
      const resp = await api.post('/api/demo/load-samples');
      const stats = resp.data.stats || {};
      const total = Object.values(stats).reduce<number>(
        (sum, v) => sum + (typeof v === 'number' ? v : 0),
        0,
      );
      setResult(
        `${t('empty.samples_loaded')} (${total})`,
      );
      trackUsage('seed_load', { resource_type: 'phase_v_seed', metadata: stats });
      if (onSamplesLoaded) onSamplesLoaded();
    } catch (e) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg || t('empty.samples_failed'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardContent className="py-12 text-center">
        <div className="mx-auto text-slate-300 mb-4 flex justify-center">{icon}</div>
        <p className="text-slate-700 font-medium">{title}</p>
        <p className="text-sm text-slate-500 mt-1 max-w-md mx-auto leading-6">{hint}</p>
        <div className="mt-5 flex flex-wrap items-center justify-center gap-2">
          {primaryAction}
          {showLoadSamples && canSeed && (
            <Button
              variant="outline"
              onClick={handleLoad}
              disabled={loading}
              className="gap-2"
            >
              <PlayCircle size={16} />
              {loading ? t('empty.loading_samples') : t('empty.load_samples')}
            </Button>
          )}
          <Link to="/demo-flows">
            <Button variant="ghost" className="gap-2">
              <Compass size={16} />
              {isAr ? 'تدفقات العرض' : 'View Demo Flows'}
            </Button>
          </Link>
        </div>
        {result && <p className="text-xs text-green-700 mt-3">{result}</p>}
        {error && <p className="text-xs text-red-600 mt-3">{error}</p>}
      </CardContent>
    </Card>
  );
}
