import { useState, useEffect, useCallback } from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import api from '@/services/api';
import { Button } from '@/components/ui/button';
import { TrendingUp, TrendingDown, Minus, RefreshCw, Camera, BarChart3 } from 'lucide-react';

interface TrendPoint {
  date: string;
  value: number;
}

interface MetricLatest {
  value: number;
  date: string | null;
  breakdown?: Record<string, number>;
}

interface TrendsData {
  latest: Record<string, MetricLatest>;
  history: Record<string, TrendPoint[]>;
  metric_keys: string[];
}

const METRIC_COLORS: Record<string, string> = {
  high_risk_obligations: '#ef4444',
  unmapped_obligations: '#f97316',
  controls_without_evidence: '#eab308',
  expired_evidence: '#dc2626',
  expiring_evidence: '#f59e0b',
  review_backlog: '#8b5cf6',
  total_obligations: '#3b82f6',
  total_controls: '#06b6d4',
  total_evidence: '#10b981',
  avg_risk_score: '#e11d48',
  control_coverage_pct: '#22c55e',
  evidence_coverage_pct: '#14b8a6',
};

export default function RiskTrendsDashboard() {
  const { t, language } = useLanguage();
  const [trends, setTrends] = useState<TrendsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [capturing, setCapturing] = useState(false);
  const [captureResult, setCaptureResult] = useState<string | null>(null);

  const loadTrends = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/api/phase5b/trends');
      setTrends(res.data);
    } catch { /* ignore */ }
    setLoading(false);
  }, []);

  useEffect(() => { loadTrends(); }, [loadTrends]);

  const handleCapture = async () => {
    setCapturing(true);
    setCaptureResult(null);
    try {
      const res = await api.post('/api/phase5b/trends/snapshot');
      setCaptureResult(
        language === 'ar'
          ? `تم التقاط ${res.data.snapshots_created} مقياس`
          : `Captured ${res.data.snapshots_created} metrics`
      );
      loadTrends();
    } catch {
      setCaptureResult(language === 'ar' ? 'فشل في التقاط اللقطة' : 'Failed to capture snapshot');
    }
    setCapturing(false);
  };

  const getTrendDirection = (points: TrendPoint[]): 'up' | 'down' | 'flat' => {
    if (!points || points.length < 2) return 'flat';
    const last = points[points.length - 1].value;
    const prev = points[points.length - 2].value;
    if (last > prev) return 'up';
    if (last < prev) return 'down';
    return 'flat';
  };

  const isPositiveMetric = (key: string): boolean => {
    return ['total_obligations', 'total_controls', 'total_evidence',
      'control_coverage_pct', 'evidence_coverage_pct'].includes(key);
  };

  const renderTrendIcon = (key: string, points: TrendPoint[]) => {
    const dir = getTrendDirection(points);
    const positive = isPositiveMetric(key);
    if (dir === 'flat') return <Minus size={16} className="text-slate-400" />;
    if (dir === 'up') {
      return positive
        ? <TrendingUp size={16} className="text-green-500" />
        : <TrendingUp size={16} className="text-red-500" />;
    }
    return positive
      ? <TrendingDown size={16} className="text-red-500" />
      : <TrendingDown size={16} className="text-green-500" />;
  };

  const renderSparkline = (points: TrendPoint[], color: string) => {
    if (!points || points.length === 0) return null;
    const values = points.map(p => p.value);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;
    const width = 200;
    const height = 40;
    const step = width / Math.max(values.length - 1, 1);

    const pathPoints = values.map((v, i) => {
      const x = i * step;
      const y = height - ((v - min) / range) * (height - 4) - 2;
      return `${x},${y}`;
    });
    const d = `M${pathPoints.join(' L')}`;

    return (
      <svg width={width} height={height} className="inline-block">
        <path d={d} fill="none" stroke={color} strokeWidth="2" />
        {values.length > 0 && (
          <circle
            cx={(values.length - 1) * step}
            cy={height - ((values[values.length - 1] - min) / range) * (height - 4) - 2}
            r="3"
            fill={color}
          />
        )}
      </svg>
    );
  };

  const formatValue = (key: string, value: number): string => {
    if (key.endsWith('_pct')) return `${value}%`;
    if (key === 'avg_risk_score') return value.toFixed(2);
    return Math.round(value).toString();
  };

  // Group metrics for display
  const riskMetrics = ['high_risk_obligations', 'unmapped_obligations', 'controls_without_evidence', 'expired_evidence', 'expiring_evidence', 'review_backlog'];
  const volumeMetrics = ['total_obligations', 'total_controls', 'total_evidence'];
  const coverageMetrics = ['control_coverage_pct', 'evidence_coverage_pct', 'avg_risk_score'];

  const renderMetricCard = (key: string) => {
    const latest = trends?.latest[key];
    const history = trends?.history[key] || [];
    const color = METRIC_COLORS[key] || '#64748b';

    return (
      <div key={key} className="bg-white rounded-xl border border-slate-200 p-4">
        <div className="flex items-center justify-between mb-2">
          <h4 className="text-sm font-medium text-slate-600">{t(`p5b.metric_${key}`)}</h4>
          {renderTrendIcon(key, history)}
        </div>
        <div className="flex items-end justify-between">
          <span className="text-2xl font-bold" style={{ color }}>
            {latest ? formatValue(key, latest.value) : '--'}
          </span>
          {latest?.date && (
            <span className="text-xs text-slate-400">
              {new Date(latest.date).toLocaleDateString()}
            </span>
          )}
        </div>
        <div className="mt-2">
          {history.length > 1 ? renderSparkline(history, color) : (
            <p className="text-xs text-slate-400 italic">{t('p5b.no_history')}</p>
          )}
        </div>
        {latest?.breakdown && Object.keys(latest.breakdown).length > 0 && (
          <div className="mt-2 pt-2 border-t border-slate-100">
            <p className="text-xs text-slate-500 mb-1">{t('p5b.by_regulator')}:</p>
            <div className="flex flex-wrap gap-1">
              {Object.entries(latest.breakdown).map(([reg, val]) => (
                <span key={reg} className="text-xs px-2 py-0.5 rounded bg-slate-100 text-slate-700">
                  {reg}: {val}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  };

  const renderSection = (title: string, keys: string[]) => (
    <div className="space-y-3">
      <h3 className="text-lg font-semibold text-slate-800">{title}</h3>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {keys.map(renderMetricCard)}
      </div>
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <BarChart3 className="text-blue-600" size={28} />
            {t('p5b.trends_title')}
          </h1>
          <p className="text-slate-500 mt-1">{t('p5b.trends_subtitle')}</p>
        </div>
        <div className="flex gap-2">
          <Button onClick={handleCapture} className="gap-2" disabled={capturing}>
            <Camera size={16} />
            {capturing ? t('common.loading') : t('p5b.capture_snapshot')}
          </Button>
          <Button onClick={loadTrends} variant="outline" className="gap-2">
            <RefreshCw size={16} /> {t('p4.refresh')}
          </Button>
        </div>
      </div>

      {captureResult && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm text-blue-800">
          {captureResult}
        </div>
      )}

      {loading ? (
        <div className="text-center py-12 text-slate-400">{t('common.loading')}</div>
      ) : !trends ? (
        <div className="text-center py-12">
          <BarChart3 size={48} className="mx-auto text-slate-300 mb-3" />
          <p className="text-slate-500">{t('p5b.no_trends_data')}</p>
          <p className="text-sm text-slate-400 mt-1">{t('p5b.capture_hint')}</p>
        </div>
      ) : (
        <>
          {/* Risk indicators */}
          {renderSection(t('p5b.section_risk'), riskMetrics)}

          {/* Volume metrics */}
          {renderSection(t('p5b.section_volume'), volumeMetrics)}

          {/* Coverage metrics */}
          {renderSection(t('p5b.section_coverage'), coverageMetrics)}

          {/* Data provenance note */}
          <div className="bg-slate-50 rounded-lg border border-slate-200 p-4 text-sm text-slate-600">
            <p className="font-medium mb-1">{t('p5b.provenance_title')}</p>
            <p>{t('p5b.provenance_desc')}</p>
          </div>
        </>
      )}
    </div>
  );
}
