import { useState, useEffect, useCallback } from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import api from '@/services/api';
import { Button } from '@/components/ui/button';
import { Clock, RefreshCw, Activity } from 'lucide-react';

interface FreshnessItem {
  regulator_id: string;
  regulator_name: string;
  regulator_name_ar?: string;
  freshness_status: string;
  confidence_score: number;
  days_since_update: number;
  expected_update_frequency_days: number;
  total_documents: number;
  total_provisions: number;
  total_obligations: number;
  pending_reviews: number;
  changes_detected: number;
  last_checked?: string;
}

export default function FreshnessDashboardPage() {
  const { t, language } = useLanguage();
  const [items, setItems] = useState<FreshnessItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [computing, setComputing] = useState(false);

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/api/phase-r/freshness/dashboard');
      setItems(res.data.regulators || []);
    } catch { /* ignore */ }
    setLoading(false);
  }, []);

  useEffect(() => { loadDashboard(); }, [loadDashboard]);

  const handleCompute = async () => {
    setComputing(true);
    try {
      await api.post('/api/phase-r/freshness/compute');
      loadDashboard();
    } catch { /* ignore */ }
    setComputing(false);
  };

  const statusColors: Record<string, string> = {
    current: 'bg-green-100 text-green-800 border-green-300',
    aging: 'bg-amber-100 text-amber-800 border-amber-300',
    stale: 'bg-red-100 text-red-800 border-red-300',
    unknown: 'bg-slate-100 text-slate-600 border-slate-300',
  };

  const statusBg: Record<string, string> = {
    current: 'bg-green-500',
    aging: 'bg-amber-500',
    stale: 'bg-red-500',
    unknown: 'bg-slate-400',
  };

  const getConfidenceColor = (score: number) => {
    if (score >= 0.8) return 'text-green-600';
    if (score >= 0.5) return 'text-amber-600';
    return 'text-red-600';
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <Activity className="text-green-600" size={28} />
            {t('pr.freshness_title')}
          </h1>
          <p className="text-slate-500 mt-1">{t('pr.freshness_subtitle')}</p>
        </div>
        <div className="flex gap-2">
          <Button onClick={handleCompute} className="gap-2" disabled={computing}>
            <Clock size={16} /> {computing ? t('common.loading') : t('pr.compute_freshness')}
          </Button>
          <Button onClick={loadDashboard} variant="outline" size="icon">
            <RefreshCw size={16} />
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-12 text-slate-400">{t('common.loading')}</div>
      ) : items.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center">
          <Clock className="mx-auto text-slate-300 mb-3" size={32} />
          <p className="text-slate-500">{t('pr.no_freshness')}</p>
          <p className="text-xs text-slate-400 mt-1">{t('pr.no_freshness_hint')}</p>
        </div>
      ) : (
        <div className="space-y-4">
          {items.map(item => (
            <div
              key={item.regulator_id}
              className={`rounded-xl border p-5 ${statusColors[item.freshness_status] || 'bg-white border-slate-200'}`}
            >
              <div className="flex items-start justify-between gap-4 mb-4">
                <div>
                  <div className="flex items-center gap-3 mb-1">
                    <h3 className="text-lg font-semibold text-slate-900">
                      {language === 'ar' && item.regulator_name_ar ? item.regulator_name_ar : item.regulator_name}
                    </h3>
                    <span className={`px-2 py-0.5 rounded-full text-xs font-bold text-white ${statusBg[item.freshness_status] || 'bg-slate-400'}`}>
                      {t(`pr.${item.freshness_status}`)}
                    </span>
                  </div>
                </div>
                <div className="text-right">
                  <p className={`text-2xl font-bold ${getConfidenceColor(item.confidence_score)}`}>
                    {(item.confidence_score * 100).toFixed(0)}%
                  </p>
                  <p className="text-xs text-slate-500">{t('pr.confidence_score')}</p>
                </div>
              </div>

              {/* Confidence bar */}
              <div className="w-full bg-white/50 rounded-full h-2 mb-4">
                <div
                  className={`h-2 rounded-full ${item.confidence_score >= 0.8 ? 'bg-green-500' : item.confidence_score >= 0.5 ? 'bg-amber-500' : 'bg-red-500'}`}
                  style={{ width: `${item.confidence_score * 100}%` }}
                />
              </div>

              {/* Stats grid */}
              <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3 text-sm">
                <div className="bg-white/60 rounded-lg p-2 text-center">
                  <p className="font-bold text-slate-800">{item.days_since_update}</p>
                  <p className="text-xs text-slate-500">{t('pr.days_since_update')}</p>
                </div>
                <div className="bg-white/60 rounded-lg p-2 text-center">
                  <p className="font-bold text-slate-800">{item.expected_update_frequency_days}d</p>
                  <p className="text-xs text-slate-500">{t('pr.expected_frequency')}</p>
                </div>
                <div className="bg-white/60 rounded-lg p-2 text-center">
                  <p className="font-bold text-slate-800">{item.total_documents}</p>
                  <p className="text-xs text-slate-500">{t('pr.total_documents')}</p>
                </div>
                <div className="bg-white/60 rounded-lg p-2 text-center">
                  <p className="font-bold text-slate-800">{item.total_provisions}</p>
                  <p className="text-xs text-slate-500">{t('pr.total_provisions_label')}</p>
                </div>
                <div className="bg-white/60 rounded-lg p-2 text-center">
                  <p className="font-bold text-slate-800">{item.total_obligations}</p>
                  <p className="text-xs text-slate-500">{t('pr.total_obligations_label')}</p>
                </div>
                <div className="bg-white/60 rounded-lg p-2 text-center">
                  <p className="font-bold text-slate-800">{item.pending_reviews}</p>
                  <p className="text-xs text-slate-500">{t('pr.pending_reviews')}</p>
                </div>
                <div className="bg-white/60 rounded-lg p-2 text-center">
                  <p className="font-bold text-slate-800">{item.changes_detected}</p>
                  <p className="text-xs text-slate-500">{t('pr.changes_count')}</p>
                </div>
              </div>

              {item.last_checked && (
                <p className="text-xs text-slate-400 mt-3">
                  {t('pr.last_checked')}: {new Date(item.last_checked).toLocaleString()}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
