import { useState, useEffect, useCallback } from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import api from '@/services/api';
import { Button } from '@/components/ui/button';
import { Search, AlertTriangle, Shield, FileWarning, Building2, Layers, RefreshCw, ChevronDown, ChevronUp } from 'lucide-react';

interface PatternItem {
  id: string;
  pattern_type: string;
  title: string;
  title_ar?: string;
  description: string;
  description_ar?: string;
  severity: string;
  confidence: number;
  affected_items?: Record<string, unknown>;
  pattern_data?: Record<string, unknown>;
  recommendation?: string;
  recommendation_ar?: string;
  is_active: boolean;
  last_detected?: string;
}

interface PatternsData {
  count: number;
  patterns: PatternItem[];
  pattern_types: string[];
}

const PATTERN_ICONS: Record<string, typeof AlertTriangle> = {
  control_risk_association: Shield,
  persistent_evidence_gap: FileWarning,
  recurring_control_weakness: AlertTriangle,
  obligation_type_risk_cluster: Layers,
  regulator_risk_concentration: Building2,
};

const SEVERITY_STYLES: Record<string, { bg: string; border: string; badge: string }> = {
  critical: { bg: 'bg-red-50', border: 'border-red-200', badge: 'bg-red-600' },
  high: { bg: 'bg-orange-50', border: 'border-orange-200', badge: 'bg-orange-500' },
  medium: { bg: 'bg-amber-50', border: 'border-amber-200', badge: 'bg-amber-500' },
  low: { bg: 'bg-green-50', border: 'border-green-200', badge: 'bg-green-500' },
};

export default function PatternDetectionPage() {
  const { t, language } = useLanguage();
  const [data, setData] = useState<PatternsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [detecting, setDetecting] = useState(false);
  const [filterType, setFilterType] = useState<string>('');
  const [filterSeverity, setFilterSeverity] = useState<string>('');
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const loadPatterns = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (filterType) params.pattern_type = filterType;
      if (filterSeverity) params.severity = filterSeverity;
      const res = await api.get('/api/phase5b/patterns', { params });
      setData(res.data);
    } catch { /* ignore */ }
    setLoading(false);
  }, [filterType, filterSeverity]);

  useEffect(() => { loadPatterns(); }, [loadPatterns]);

  const handleDetect = async () => {
    setDetecting(true);
    try {
      await api.post('/api/phase5b/patterns/detect');
      loadPatterns();
    } catch { /* ignore */ }
    setDetecting(false);
  };

  const renderPatternCard = (pattern: PatternItem) => {
    const Icon = PATTERN_ICONS[pattern.pattern_type] || AlertTriangle;
    const styles = SEVERITY_STYLES[pattern.severity] || SEVERITY_STYLES.medium;
    const isExpanded = expandedId === pattern.id;
    const title = language === 'ar' && pattern.title_ar ? pattern.title_ar : pattern.title;
    const desc = language === 'ar' && pattern.description_ar ? pattern.description_ar : pattern.description;
    const rec = language === 'ar' && pattern.recommendation_ar ? pattern.recommendation_ar : pattern.recommendation;

    return (
      <div key={pattern.id} className={`rounded-xl border ${styles.border} ${styles.bg} overflow-hidden`}>
        <button
          className="w-full p-4 flex items-start gap-4 text-left"
          onClick={() => setExpandedId(isExpanded ? null : pattern.id)}
        >
          <div className="mt-0.5">
            <Icon size={22} className="text-slate-700" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap mb-1">
              <span className={`px-2 py-0.5 rounded-full text-xs font-bold text-white ${styles.badge}`}>
                {t(`p4.severity_${pattern.severity}`)}
              </span>
              <span className="px-2 py-0.5 rounded text-xs bg-white/60 text-slate-600">
                {t(`p5b.type_${pattern.pattern_type}`)}
              </span>
              <span className="text-xs text-slate-500">
                {t('p5b.confidence')}: {Math.round(pattern.confidence * 100)}%
              </span>
            </div>
            <h4 className="font-medium text-slate-900 text-sm">{title}</h4>
          </div>
          <div className="flex-shrink-0">
            {isExpanded ? <ChevronUp size={16} className="text-slate-400" /> : <ChevronDown size={16} className="text-slate-400" />}
          </div>
        </button>

        {isExpanded && (
          <div className="border-t border-slate-200/60 p-4 space-y-3">
            <div>
              <h5 className="text-xs font-semibold text-slate-500 uppercase mb-1">{t('p5b.description')}</h5>
              <p className="text-sm text-slate-700">{desc}</p>
            </div>

            {rec && (
              <div className="bg-white/70 rounded-lg p-3">
                <h5 className="text-xs font-semibold text-slate-500 uppercase mb-1">{t('p5b.recommendation')}</h5>
                <p className="text-sm text-slate-700">{rec}</p>
              </div>
            )}

            {pattern.pattern_data && Object.keys(pattern.pattern_data).length > 0 && (
              <div>
                <h5 className="text-xs font-semibold text-slate-500 uppercase mb-1">{t('p5b.supporting_data')}</h5>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(pattern.pattern_data).map(([k, v]) => (
                    <span key={k} className="text-xs px-2 py-1 rounded bg-white/80 text-slate-600 border border-slate-200">
                      {k.replace(/_/g, ' ')}: <strong>{String(v)}</strong>
                    </span>
                  ))}
                </div>
              </div>
            )}

            {pattern.last_detected && (
              <p className="text-xs text-slate-400">
                {t('p5b.last_detected')}: {new Date(pattern.last_detected).toLocaleString()}
              </p>
            )}
          </div>
        )}
      </div>
    );
  };

  // Group patterns by type
  const groupedPatterns: Record<string, PatternItem[]> = {};
  if (data?.patterns) {
    for (const p of data.patterns) {
      if (!groupedPatterns[p.pattern_type]) groupedPatterns[p.pattern_type] = [];
      groupedPatterns[p.pattern_type].push(p);
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <Search className="text-purple-600" size={28} />
            {t('p5b.patterns_title')}
          </h1>
          <p className="text-slate-500 mt-1">{t('p5b.patterns_subtitle')}</p>
        </div>
        <div className="flex gap-2">
          <Button onClick={handleDetect} className="gap-2" disabled={detecting}>
            <Search size={16} />
            {detecting ? t('common.loading') : t('p5b.run_detection')}
          </Button>
          <Button onClick={loadPatterns} variant="outline" className="gap-2">
            <RefreshCw size={16} /> {t('p4.refresh')}
          </Button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-4 flex-wrap">
        <select
          className="px-3 py-2 border rounded-lg text-sm"
          value={filterType}
          onChange={e => setFilterType(e.target.value)}
        >
          <option value="">{t('p5b.all_types')}</option>
          {(data?.pattern_types || []).map(pt => (
            <option key={pt} value={pt}>{t(`p5b.type_${pt}`)}</option>
          ))}
        </select>
        <select
          className="px-3 py-2 border rounded-lg text-sm"
          value={filterSeverity}
          onChange={e => setFilterSeverity(e.target.value)}
        >
          <option value="">{t('p5b.all_severities')}</option>
          <option value="critical">{t('p4.severity_critical')}</option>
          <option value="high">{t('p4.severity_high')}</option>
          <option value="medium">{t('p4.severity_medium')}</option>
          <option value="low">{t('p4.severity_low')}</option>
        </select>
      </div>

      {/* Summary bar */}
      {data && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-white rounded-xl border border-slate-200 p-4 text-center">
            <p className="text-2xl font-bold text-slate-900">{data.count}</p>
            <p className="text-xs text-slate-500 mt-1">{t('p5b.active_patterns')}</p>
          </div>
          <div className="bg-red-50 rounded-xl border border-red-200 p-4 text-center">
            <p className="text-2xl font-bold text-red-700">
              {data.patterns.filter(p => p.severity === 'critical').length}
            </p>
            <p className="text-xs text-red-600 mt-1">{t('p4.severity_critical')}</p>
          </div>
          <div className="bg-orange-50 rounded-xl border border-orange-200 p-4 text-center">
            <p className="text-2xl font-bold text-orange-700">
              {data.patterns.filter(p => p.severity === 'high').length}
            </p>
            <p className="text-xs text-orange-600 mt-1">{t('p4.severity_high')}</p>
          </div>
          <div className="bg-amber-50 rounded-xl border border-amber-200 p-4 text-center">
            <p className="text-2xl font-bold text-amber-700">
              {data.patterns.filter(p => p.severity === 'medium').length}
            </p>
            <p className="text-xs text-amber-600 mt-1">{t('p4.severity_medium')}</p>
          </div>
        </div>
      )}

      {loading ? (
        <div className="text-center py-12 text-slate-400">{t('common.loading')}</div>
      ) : !data || data.count === 0 ? (
        <div className="text-center py-12">
          <Search size={48} className="mx-auto text-slate-300 mb-3" />
          <p className="text-slate-500">{t('p5b.no_patterns')}</p>
          <p className="text-sm text-slate-400 mt-1">{t('p5b.detect_hint')}</p>
        </div>
      ) : (
        <>
          {/* Patterns grouped by type */}
          {Object.entries(groupedPatterns).map(([type, patterns]) => (
            <div key={type} className="space-y-3">
              <h3 className="text-lg font-semibold text-slate-800 flex items-center gap-2">
                {(() => { const Icon = PATTERN_ICONS[type] || AlertTriangle; return <Icon size={20} />; })()}
                {t(`p5b.type_${type}`)}
                <span className="text-sm font-normal text-slate-500">({patterns.length})</span>
              </h3>
              <div className="space-y-2">
                {patterns.map(renderPatternCard)}
              </div>
            </div>
          ))}

          {/* Explainability disclaimer */}
          <div className="bg-slate-50 rounded-lg border border-slate-200 p-4 text-sm text-slate-600">
            <p className="font-medium mb-1">{t('p5b.explainability_title')}</p>
            <p>{t('p5b.explainability_desc')}</p>
          </div>
        </>
      )}
    </div>
  );
}
