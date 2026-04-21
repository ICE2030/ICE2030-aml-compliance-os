import { useState, useEffect, useCallback } from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import api from '@/services/api';
import { Button } from '@/components/ui/button';
import { Bell, AlertTriangle, Clock, CheckCircle, RefreshCw, ChevronDown, ChevronUp } from 'lucide-react';

interface AlertItem {
  evidence_id: string;
  evidence_name: string;
  evidence_name_ar?: string;
  artifact_type: string;
  owner?: string;
  control_id: string;
  control_name: string;
  control_name_ar?: string;
  obligations_affected: number;
  expires_at: string;
  status: string;
  periodicity?: string;
  days_overdue?: number;
  days_until_expiry?: number;
  severity: string;
  alert_type: string;
}

interface AlertSummary {
  total_evidence: number;
  total_with_expiry: number;
  total_without_expiry: number;
  expired_count: number;
  expiring_soon_count: number;
  healthy_count: number;
  days_ahead_window: number;
  checked_at: string;
}

interface AlertsData {
  expired: AlertItem[];
  expiring_soon: AlertItem[];
  summary: AlertSummary;
}

export default function EvidenceAlertsPage() {
  const { t, language } = useLanguage();
  const [alerts, setAlerts] = useState<AlertsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [daysAhead, setDaysAhead] = useState(30);
  const [expandedSection, setExpandedSection] = useState<string>('expired');
  const [autoMarking, setAutoMarking] = useState(false);

  const loadAlerts = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/api/phase5a/alerts/evidence-expiry', {
        params: { days_ahead: daysAhead },
      });
      setAlerts(res.data);
    } catch { /* ignore */ }
    setLoading(false);
  }, [daysAhead]);

  useEffect(() => { loadAlerts(); }, [loadAlerts]);

  const handleAutoMark = async () => {
    setAutoMarking(true);
    try {
      await api.post('/api/phase5a/alerts/evidence-expiry/auto-mark');
      loadAlerts();
    } catch { /* ignore */ }
    setAutoMarking(false);
  };

  const severityColors: Record<string, string> = {
    critical: 'bg-red-100 text-red-800 border-red-300',
    high: 'bg-orange-100 text-orange-800 border-orange-300',
    medium: 'bg-amber-100 text-amber-800 border-amber-300',
    low: 'bg-green-100 text-green-800 border-green-300',
  };

  const severityBadge: Record<string, string> = {
    critical: 'bg-red-600', high: 'bg-orange-500',
    medium: 'bg-amber-500', low: 'bg-green-500',
  };

  const renderAlertItem = (item: AlertItem) => (
    <div
      key={item.evidence_id}
      className={`rounded-lg border p-4 ${severityColors[item.severity] || 'bg-slate-50 border-slate-200'}`}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-3 flex-wrap">
            <h4 className="font-medium text-slate-900">
              {language === 'ar' && item.evidence_name_ar ? item.evidence_name_ar : item.evidence_name}
            </h4>
            <span className={`px-2 py-0.5 rounded-full text-xs font-bold text-white ${severityBadge[item.severity] || 'bg-slate-400'}`}>
              {t(`p4.severity_${item.severity}`)}
            </span>
            <span className="px-2 py-0.5 rounded text-xs bg-white/60">{item.artifact_type}</span>
          </div>

          <div className="mt-2 text-sm text-slate-700">
            <span className="font-medium">{t('p5a.linked_control')}:</span>{' '}
            {language === 'ar' && item.control_name_ar ? item.control_name_ar : item.control_name}
          </div>

          <div className="flex gap-4 mt-2 text-xs text-slate-500 flex-wrap">
            {item.owner && <span>{t('p4.owner')}: {item.owner}</span>}
            <span>{t('p5a.expires_at')}: {new Date(item.expires_at).toLocaleDateString()}</span>
            {item.days_overdue !== undefined && (
              <span className="font-bold text-red-700">
                {item.days_overdue} {t('p5a.days_overdue')}
              </span>
            )}
            {item.days_until_expiry !== undefined && (
              <span className="font-bold text-amber-700">
                {item.days_until_expiry} {t('p5a.days_until_expiry')}
              </span>
            )}
            {item.obligations_affected > 0 && (
              <span>{item.obligations_affected} {t('p5a.obligations_affected')}</span>
            )}
            {item.periodicity && <span>{t('p4.periodicity')}: {item.periodicity}</span>}
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <Bell className="text-red-500" size={28} />
            {t('p5a.alerts_title')}
          </h1>
          <p className="text-slate-500 mt-1">{t('p5a.alerts_subtitle')}</p>
        </div>
        <div className="flex gap-2">
          <Button onClick={handleAutoMark} variant="outline" className="gap-2" disabled={autoMarking}>
            <AlertTriangle size={16} />
            {autoMarking ? t('common.loading') : t('p5a.auto_mark_expired')}
          </Button>
          <Button onClick={loadAlerts} variant="outline" className="gap-2">
            <RefreshCw size={16} /> {t('p4.refresh')}
          </Button>
        </div>
      </div>

      {/* Days ahead filter */}
      <div className="flex items-center gap-3">
        <label className="text-sm text-slate-600">{t('p5a.days_ahead_label')}:</label>
        <select
          className="px-3 py-2 border rounded-lg text-sm"
          value={daysAhead}
          onChange={e => setDaysAhead(Number(e.target.value))}
        >
          <option value={7}>7 {t('p5a.days')}</option>
          <option value={14}>14 {t('p5a.days')}</option>
          <option value={30}>30 {t('p5a.days')}</option>
          <option value={60}>60 {t('p5a.days')}</option>
          <option value={90}>90 {t('p5a.days')}</option>
        </select>
      </div>

      {loading ? (
        <div className="text-center py-12 text-slate-400">{t('common.loading')}</div>
      ) : !alerts ? (
        <div className="text-center py-12 text-slate-400">{t('common.no_data')}</div>
      ) : (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div className="bg-white rounded-xl border border-slate-200 p-4 text-center">
              <p className="text-2xl font-bold text-slate-900">{alerts.summary.total_evidence}</p>
              <p className="text-xs text-slate-500 mt-1">{t('p5a.total_evidence')}</p>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 p-4 text-center">
              <p className="text-2xl font-bold text-slate-900">{alerts.summary.total_with_expiry}</p>
              <p className="text-xs text-slate-500 mt-1">{t('p5a.with_expiry')}</p>
            </div>
            <div className="bg-red-50 rounded-xl border border-red-200 p-4 text-center">
              <p className="text-2xl font-bold text-red-700">{alerts.summary.expired_count}</p>
              <p className="text-xs text-red-600 mt-1">{t('p5a.expired')}</p>
            </div>
            <div className="bg-amber-50 rounded-xl border border-amber-200 p-4 text-center">
              <p className="text-2xl font-bold text-amber-700">{alerts.summary.expiring_soon_count}</p>
              <p className="text-xs text-amber-600 mt-1">{t('p5a.expiring_soon')}</p>
            </div>
            <div className="bg-green-50 rounded-xl border border-green-200 p-4 text-center">
              <p className="text-2xl font-bold text-green-700">{alerts.summary.healthy_count}</p>
              <p className="text-xs text-green-600 mt-1">{t('p5a.healthy')}</p>
            </div>
          </div>

          {/* Expired section */}
          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
            <button
              className="w-full p-4 flex items-center justify-between text-left hover:bg-slate-50"
              onClick={() => setExpandedSection(expandedSection === 'expired' ? '' : 'expired')}
            >
              <div className="flex items-center gap-3">
                <AlertTriangle className="text-red-500" size={20} />
                <span className="font-semibold text-slate-900">{t('p5a.expired_section')}</span>
                <span className="text-sm text-red-600 font-medium">({alerts.expired.length})</span>
              </div>
              {expandedSection === 'expired' ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </button>
            {expandedSection === 'expired' && (
              <div className="border-t p-4 space-y-3">
                {alerts.expired.length === 0 ? (
                  <div className="text-center py-6 text-slate-400 flex items-center justify-center gap-2">
                    <CheckCircle size={16} className="text-green-500" />
                    {t('p5a.no_expired')}
                  </div>
                ) : (
                  alerts.expired.map(renderAlertItem)
                )}
              </div>
            )}
          </div>

          {/* Expiring soon section */}
          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
            <button
              className="w-full p-4 flex items-center justify-between text-left hover:bg-slate-50"
              onClick={() => setExpandedSection(expandedSection === 'expiring' ? '' : 'expiring')}
            >
              <div className="flex items-center gap-3">
                <Clock className="text-amber-500" size={20} />
                <span className="font-semibold text-slate-900">{t('p5a.expiring_soon_section')}</span>
                <span className="text-sm text-amber-600 font-medium">({alerts.expiring_soon.length})</span>
              </div>
              {expandedSection === 'expiring' ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </button>
            {expandedSection === 'expiring' && (
              <div className="border-t p-4 space-y-3">
                {alerts.expiring_soon.length === 0 ? (
                  <div className="text-center py-6 text-slate-400 flex items-center justify-center gap-2">
                    <CheckCircle size={16} className="text-green-500" />
                    {t('p5a.no_expiring_soon')}
                  </div>
                ) : (
                  alerts.expiring_soon.map(renderAlertItem)
                )}
              </div>
            )}
          </div>

          {/* Checked at footer */}
          <p className="text-xs text-slate-400 text-center">
            {t('p5a.last_checked')}: {new Date(alerts.summary.checked_at).toLocaleString()}
          </p>
        </>
      )}
    </div>
  );
}
