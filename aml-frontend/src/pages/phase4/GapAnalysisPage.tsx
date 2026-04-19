import { useState, useEffect } from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import api from '@/services/api';
import { Button } from '@/components/ui/button';
import { AlertTriangle, Shield, FileText, Search, RefreshCw } from 'lucide-react';

interface GapSummary {
  total_obligations: number;
  obligations_without_controls: number;
  controls_without_evidence: number;
  high_risk_obligations: number;
  obligations_needing_review: number;
}

interface Gap {
  obligation_id: string;
  obligation_text: string;
  obligation_type: string;
  review_status: string;
  regulator?: string;
  source_title?: string;
  risk_severity?: string;
  risk_score?: number;
  control_name?: string;
}

export default function GapAnalysisPage() {
  const { t } = useLanguage();
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState<GapSummary | null>(null);
  const [gaps, setGaps] = useState<Record<string, Gap[]>>({});
  const [activeTab, setActiveTab] = useState('unmapped');
  const [scoring, setScoring] = useState(false);

  const loadGaps = async () => {
    setLoading(true);
    try {
      const res = await api.get('/api/phase4/gaps');
      setSummary(res.data.summary || null);
      setGaps(res.data.gaps || {});
    } catch { /* ignore */ }
    setLoading(false);
  };

  useEffect(() => { loadGaps(); }, []);

  const handleScoreAll = async () => {
    setScoring(true);
    try {
      await api.get('/api/phase4/risks/score-all');
      await loadGaps();
    } catch { /* ignore */ }
    setScoring(false);
  };

  const tabs = [
    { key: 'unmapped', label: t('p4.gap_unmapped'), icon: Shield, count: summary?.obligations_without_controls || 0, color: 'text-red-600' },
    { key: 'no_evidence', label: t('p4.gap_no_evidence'), icon: FileText, count: summary?.controls_without_evidence || 0, color: 'text-amber-600' },
    { key: 'high_risk', label: t('p4.gap_high_risk'), icon: AlertTriangle, count: summary?.high_risk_obligations || 0, color: 'text-red-600' },
    { key: 'needs_review', label: t('p4.gap_needs_review'), icon: Search, count: summary?.obligations_needing_review || 0, color: 'text-blue-600' },
  ];

  const severityColors: Record<string, string> = {
    critical: 'bg-red-100 text-red-800 border-red-200',
    high: 'bg-orange-100 text-orange-800 border-orange-200',
    medium: 'bg-amber-100 text-amber-800 border-amber-200',
    low: 'bg-green-100 text-green-800 border-green-200',
  };

  const currentGaps = gaps[activeTab] || [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <AlertTriangle className="text-amber-600" size={28} />
            {t('p4.gap_title')}
          </h1>
          <p className="text-slate-500 mt-1">{t('p4.gap_subtitle')}</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleScoreAll} disabled={scoring} className="gap-2">
            <RefreshCw size={16} className={scoring ? 'animate-spin' : ''} />
            {t('p4.score_all_risks')}
          </Button>
          <Button variant="outline" onClick={loadGaps} className="gap-2">
            <RefreshCw size={16} /> {t('p4.refresh')}
          </Button>
        </div>
      </div>

      {/* Summary cards */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className="bg-white rounded-xl border p-4 text-center">
            <p className="text-2xl font-bold text-slate-900">{summary.total_obligations}</p>
            <p className="text-xs text-slate-500">{t('p4.total_obligations')}</p>
          </div>
          <div className="bg-white rounded-xl border border-red-200 p-4 text-center">
            <p className="text-2xl font-bold text-red-600">{summary.obligations_without_controls}</p>
            <p className="text-xs text-slate-500">{t('p4.gap_unmapped')}</p>
          </div>
          <div className="bg-white rounded-xl border border-amber-200 p-4 text-center">
            <p className="text-2xl font-bold text-amber-600">{summary.controls_without_evidence}</p>
            <p className="text-xs text-slate-500">{t('p4.gap_no_evidence')}</p>
          </div>
          <div className="bg-white rounded-xl border border-red-200 p-4 text-center">
            <p className="text-2xl font-bold text-red-600">{summary.high_risk_obligations}</p>
            <p className="text-xs text-slate-500">{t('p4.gap_high_risk')}</p>
          </div>
          <div className="bg-white rounded-xl border border-blue-200 p-4 text-center">
            <p className="text-2xl font-bold text-blue-600">{summary.obligations_needing_review}</p>
            <p className="text-xs text-slate-500">{t('p4.gap_needs_review')}</p>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2 border-b">
        {tabs.map(tab => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.key
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-slate-500 hover:text-slate-700'
              }`}
            >
              <Icon size={16} className={activeTab === tab.key ? tab.color : ''} />
              {tab.label}
              <span className={`px-1.5 py-0.5 rounded-full text-xs ${
                activeTab === tab.key ? 'bg-blue-100 text-blue-700' : 'bg-slate-100 text-slate-600'
              }`}>
                {tab.count}
              </span>
            </button>
          );
        })}
      </div>

      {/* Gap items */}
      {loading ? (
        <div className="text-center py-12 text-slate-400">{t('common.loading')}</div>
      ) : currentGaps.length === 0 ? (
        <div className="text-center py-12 bg-white rounded-xl border">
          <Shield className="mx-auto text-green-400" size={48} />
          <p className="text-green-600 mt-3 font-medium">{t('p4.no_gaps')}</p>
          <p className="text-sm text-slate-400 mt-1">{t('p4.no_gaps_desc')}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {currentGaps.map((gap, idx) => (
            <div key={gap.obligation_id || idx} className="bg-white rounded-xl border border-slate-200 p-4">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <p className="text-slate-900 text-sm">
                    {(activeTab === 'no_evidence' && gap.control_name)
                      ? gap.control_name
                      : (gap.obligation_text?.substring(0, 250) + ((gap.obligation_text?.length || 0) > 250 ? '...' : ''))}
                  </p>
                  <div className="flex gap-2 mt-2 flex-wrap">
                    {gap.obligation_type && (
                      <span className="bg-slate-100 text-slate-600 px-2 py-0.5 rounded text-xs">{gap.obligation_type}</span>
                    )}
                    {gap.review_status && (
                      <span className="bg-slate-100 text-slate-600 px-2 py-0.5 rounded text-xs">{gap.review_status}</span>
                    )}
                    {gap.regulator && (
                      <span className="bg-blue-50 text-blue-700 px-2 py-0.5 rounded text-xs">{gap.regulator}</span>
                    )}
                    {gap.source_title && (
                      <span className="bg-purple-50 text-purple-700 px-2 py-0.5 rounded text-xs">{gap.source_title}</span>
                    )}
                  </div>
                </div>
                {gap.risk_severity && (
                  <div className={`px-3 py-1 rounded-lg text-xs font-medium border ${severityColors[gap.risk_severity] || 'bg-slate-100'}`}>
                    {t(`p4.severity_${gap.risk_severity}`)}
                    {gap.risk_score !== undefined && (
                      <span className="ms-1">({(gap.risk_score * 100).toFixed(0)}%)</span>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
