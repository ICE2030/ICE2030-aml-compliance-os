import { useState, useEffect, useCallback } from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import api from '@/services/api';
import { Button } from '@/components/ui/button';
import { GitCompare, RefreshCw, Play, Database, AlertTriangle } from 'lucide-react';

interface ChangeItem {
  id: string;
  document_id: string;
  provision_id?: string;
  change_scope: string;
  classification: string;
  summary: string;
  summary_ar?: string;
  detected_at?: string;
  review_status: string;
  before_snapshot_id?: string;
  after_snapshot_id?: string;
}

interface BaselineResult {
  total_provisions: number;
  snapshots_created: number;
  snapshots_skipped: number;
  snapshot_at: string;
}

interface DetectResult {
  total_provisions: number;
  new_provisions: number;
  modified_provisions: number;
  unchanged_provisions: number;
  changes_detected: number;
  changes: Array<{
    change_id: string;
    provision_id: string;
    section: string;
    scope: string;
    classification: string;
    summary: string;
  }>;
}

export default function ChangeDetectionPage() {
  const { t, language } = useLanguage();
  const [changes, setChanges] = useState<ChangeItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [baselineResult, setBaselineResult] = useState<BaselineResult | null>(null);
  const [detectResult, setDetectResult] = useState<DetectResult | null>(null);
  const [running, setRunning] = useState(false);
  const [filterClassification, setFilterClassification] = useState('');

  const loadHistory = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (filterClassification) params.classification = filterClassification;
      const res = await api.get('/api/phase-r/changes/history', { params });
      setChanges(res.data.changes || []);
    } catch { /* ignore */ }
    setLoading(false);
  }, [filterClassification]);

  useEffect(() => { loadHistory(); }, [loadHistory]);

  const handleBaseline = async () => {
    setRunning(true);
    try {
      const res = await api.post('/api/phase-r/changes/baseline');
      setBaselineResult(res.data);
      loadHistory();
    } catch { /* ignore */ }
    setRunning(false);
  };

  const handleDetect = async () => {
    setRunning(true);
    try {
      const res = await api.post('/api/phase-r/changes/detect');
      setDetectResult(res.data);
      loadHistory();
    } catch { /* ignore */ }
    setRunning(false);
  };

  const handlePipeline = async () => {
    setRunning(true);
    try {
      await api.post('/api/phase-r/pipeline/run');
      loadHistory();
    } catch { /* ignore */ }
    setRunning(false);
  };

  const classificationColors: Record<string, string> = {
    informational: 'bg-blue-100 text-blue-800',
    interpretive: 'bg-purple-100 text-purple-800',
    operational: 'bg-amber-100 text-amber-800',
    material: 'bg-red-100 text-red-800',
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <GitCompare className="text-blue-600" size={28} />
            {t('pr.change_title')}
          </h1>
          <p className="text-slate-500 mt-1">{t('pr.change_subtitle')}</p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <Button onClick={handleBaseline} variant="outline" className="gap-2" disabled={running}>
            <Database size={16} /> {t('pr.create_baseline')}
          </Button>
          <Button onClick={handleDetect} variant="outline" className="gap-2" disabled={running}>
            <GitCompare size={16} /> {t('pr.detect_changes')}
          </Button>
          <Button onClick={handlePipeline} className="gap-2" disabled={running}>
            <Play size={16} /> {t('pr.run_pipeline')}
          </Button>
          <Button onClick={loadHistory} variant="ghost" size="icon" disabled={loading}>
            <RefreshCw size={16} />
          </Button>
        </div>
      </div>

      {/* Baseline result */}
      {baselineResult && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
          <h3 className="font-semibold text-blue-900 mb-2">{t('pr.create_baseline')} — Result</h3>
          <div className="grid grid-cols-3 gap-4 text-sm">
            <div>
              <span className="text-blue-600">{t('pr.total_provisions')}:</span>{' '}
              <strong>{baselineResult.total_provisions}</strong>
            </div>
            <div>
              <span className="text-blue-600">{t('pr.snapshots_created')}:</span>{' '}
              <strong>{baselineResult.snapshots_created}</strong>
            </div>
            <div>
              <span className="text-blue-600">Skipped:</span>{' '}
              <strong>{baselineResult.snapshots_skipped}</strong>
            </div>
          </div>
        </div>
      )}

      {/* Detect result */}
      {detectResult && (
        <div className="bg-green-50 border border-green-200 rounded-xl p-4">
          <h3 className="font-semibold text-green-900 mb-2">{t('pr.detect_changes')} — Result</h3>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div className="text-center">
              <p className="text-2xl font-bold text-slate-900">{detectResult.total_provisions}</p>
              <p className="text-xs text-slate-500">{t('pr.total_provisions')}</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-blue-600">{detectResult.new_provisions}</p>
              <p className="text-xs text-blue-500">{t('pr.new_provisions')}</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-amber-600">{detectResult.modified_provisions}</p>
              <p className="text-xs text-amber-500">{t('pr.modified')}</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-green-600">{detectResult.unchanged_provisions}</p>
              <p className="text-xs text-green-500">{t('pr.unchanged')}</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-red-600">{detectResult.changes_detected}</p>
              <p className="text-xs text-red-500">{t('pr.changes_detected')}</p>
            </div>
          </div>
        </div>
      )}

      {/* Filter */}
      <div className="flex items-center gap-3">
        <label className="text-sm text-slate-600">{t('pr.classification')}:</label>
        <select
          className="px-3 py-2 border rounded-lg text-sm"
          value={filterClassification}
          onChange={e => setFilterClassification(e.target.value)}
        >
          <option value="">{t('pr.all_classifications')}</option>
          <option value="informational">{t('pr.informational')}</option>
          <option value="interpretive">{t('pr.interpretive')}</option>
          <option value="operational">{t('pr.operational')}</option>
          <option value="material">{t('pr.material')}</option>
        </select>
      </div>

      {/* Change History */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="p-4 border-b flex items-center gap-3">
          <h3 className="font-semibold text-slate-900">{t('pr.change_history')}</h3>
          <span className="text-sm text-slate-500">({changes.length})</span>
        </div>

        {loading ? (
          <div className="text-center py-12 text-slate-400">{t('common.loading')}</div>
        ) : changes.length === 0 ? (
          <div className="text-center py-12">
            <AlertTriangle className="mx-auto text-slate-300 mb-3" size={32} />
            <p className="text-slate-500">{t('pr.no_changes')}</p>
            <p className="text-xs text-slate-400 mt-1">{t('pr.no_changes_hint')}</p>
          </div>
        ) : (
          <div className="divide-y">
            {changes.map(change => (
              <div key={change.id} className="p-4 hover:bg-slate-50">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${classificationColors[change.classification] || 'bg-slate-100 text-slate-700'}`}>
                        {t(`pr.${change.classification}`)}
                      </span>
                      <span className="px-2 py-0.5 rounded text-xs bg-slate-100 text-slate-600">
                        {change.change_scope.replace(/_/g, ' ')}
                      </span>
                      <span className="px-2 py-0.5 rounded text-xs bg-slate-100 text-slate-600">
                        {change.review_status}
                      </span>
                    </div>
                    <p className="text-sm text-slate-800">
                      {language === 'ar' && change.summary_ar ? change.summary_ar : change.summary}
                    </p>
                  </div>
                  {change.detected_at && (
                    <span className="text-xs text-slate-400 whitespace-nowrap">
                      {new Date(change.detected_at).toLocaleString()}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
