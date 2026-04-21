import { useState, useEffect, useCallback } from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import api from '@/services/api';
import { Button } from '@/components/ui/button';
import { Bell, CheckCircle, Eye, XCircle, RefreshCw } from 'lucide-react';

interface AlertItem {
  id: string;
  change_id?: string;
  regulator_id: string;
  title: string;
  title_ar?: string;
  description: string;
  description_ar?: string;
  severity: string;
  alert_type: string;
  affected_obligations_count: number;
  affected_controls_count: number;
  affected_evidence_count: number;
  status: string;
  acknowledged_by?: string;
  acknowledged_at?: string;
  resolved_at?: string;
  created_at?: string;
}

export default function RegulatoryAlertsPage() {
  const { t, language } = useLanguage();
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filterSeverity, setFilterSeverity] = useState('');
  const [filterStatus, setFilterStatus] = useState('');

  const loadAlerts = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (filterSeverity) params.severity = filterSeverity;
      if (filterStatus) params.status = filterStatus;
      const res = await api.get('/api/phase-r/alerts', { params });
      setAlerts(res.data.alerts || []);
      setTotal(res.data.total || 0);
    } catch { /* ignore */ }
    setLoading(false);
  }, [filterSeverity, filterStatus]);

  useEffect(() => { loadAlerts(); }, [loadAlerts]);

  const handleAction = async (alertId: string, action: string) => {
    try {
      await api.post(`/api/phase-r/alerts/${alertId}/${action}`);
      loadAlerts();
    } catch { /* ignore */ }
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

  const statusIcon: Record<string, React.ReactNode> = {
    active: <Bell className="text-red-500" size={16} />,
    acknowledged: <Eye className="text-blue-500" size={16} />,
    resolved: <CheckCircle className="text-green-500" size={16} />,
    dismissed: <XCircle className="text-slate-400" size={16} />,
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <Bell className="text-red-500" size={28} />
            {t('pr.alerts_title')}
          </h1>
          <p className="text-slate-500 mt-1">{t('pr.alerts_subtitle')}</p>
        </div>
        <Button onClick={loadAlerts} variant="outline" className="gap-2">
          <RefreshCw size={16} /> {t('p4.refresh')}
        </Button>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-slate-200 p-4 text-center">
          <p className="text-2xl font-bold text-slate-900">{total}</p>
          <p className="text-xs text-slate-500 mt-1">{t('pr.total_alerts')}</p>
        </div>
        <div className="bg-red-50 rounded-xl border border-red-200 p-4 text-center">
          <p className="text-2xl font-bold text-red-700">{alerts.filter(a => a.status === 'active').length}</p>
          <p className="text-xs text-red-600 mt-1">{t('pr.active_alerts')}</p>
        </div>
        <div className="bg-blue-50 rounded-xl border border-blue-200 p-4 text-center">
          <p className="text-2xl font-bold text-blue-700">{alerts.filter(a => a.status === 'acknowledged').length}</p>
          <p className="text-xs text-blue-600 mt-1">{t('pr.acknowledged')}</p>
        </div>
        <div className="bg-green-50 rounded-xl border border-green-200 p-4 text-center">
          <p className="text-2xl font-bold text-green-700">{alerts.filter(a => a.status === 'resolved').length}</p>
          <p className="text-xs text-green-600 mt-1">{t('pr.resolved')}</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4 flex-wrap">
        <div className="flex items-center gap-2">
          <label className="text-sm text-slate-600">{t('pr.severity')}:</label>
          <select
            className="px-3 py-2 border rounded-lg text-sm"
            value={filterSeverity}
            onChange={e => setFilterSeverity(e.target.value)}
          >
            <option value="">{t('p5b.all_severities')}</option>
            <option value="critical">{t('common.critical')}</option>
            <option value="high">{t('common.high')}</option>
            <option value="medium">{t('common.medium')}</option>
            <option value="low">{t('common.low')}</option>
          </select>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-sm text-slate-600">{t('p4.status')}:</label>
          <select
            className="px-3 py-2 border rounded-lg text-sm"
            value={filterStatus}
            onChange={e => setFilterStatus(e.target.value)}
          >
            <option value="">{t('p4.all_statuses')}</option>
            <option value="active">{t('pr.active_alerts')}</option>
            <option value="acknowledged">{t('pr.acknowledged')}</option>
            <option value="resolved">{t('pr.resolved')}</option>
            <option value="dismissed">{t('pr.dismissed')}</option>
          </select>
        </div>
      </div>

      {/* Alerts list */}
      {loading ? (
        <div className="text-center py-12 text-slate-400">{t('common.loading')}</div>
      ) : alerts.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center">
          <CheckCircle className="mx-auto text-green-300 mb-3" size={32} />
          <p className="text-slate-500">{t('pr.no_alerts')}</p>
          <p className="text-xs text-slate-400 mt-1">{t('pr.no_alerts_hint')}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {alerts.map(alert => (
            <div
              key={alert.id}
              className={`rounded-xl border p-4 ${severityColors[alert.severity] || 'bg-white border-slate-200'}`}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-2 flex-wrap">
                    {statusIcon[alert.status]}
                    <h4 className="font-semibold text-slate-900">
                      {language === 'ar' && alert.title_ar ? alert.title_ar : alert.title}
                    </h4>
                    <span className={`px-2 py-0.5 rounded-full text-xs font-bold text-white ${severityBadge[alert.severity] || 'bg-slate-400'}`}>
                      {alert.severity.toUpperCase()}
                    </span>
                    <span className="px-2 py-0.5 rounded text-xs bg-white/60">
                      {alert.alert_type.replace(/_/g, ' ')}
                    </span>
                  </div>
                  <p className="text-sm text-slate-700 mb-2">
                    {language === 'ar' && alert.description_ar ? alert.description_ar : alert.description}
                  </p>
                  <div className="flex gap-4 text-xs text-slate-500 flex-wrap">
                    {alert.affected_obligations_count > 0 && (
                      <span>{t('pr.affected_obligations')}: {alert.affected_obligations_count}</span>
                    )}
                    {alert.affected_controls_count > 0 && (
                      <span>{t('pr.affected_controls')}: {alert.affected_controls_count}</span>
                    )}
                    {alert.affected_evidence_count > 0 && (
                      <span>{t('pr.affected_evidence')}: {alert.affected_evidence_count}</span>
                    )}
                    {alert.created_at && (
                      <span>{new Date(alert.created_at).toLocaleString()}</span>
                    )}
                  </div>
                </div>
                {alert.status === 'active' && (
                  <div className="flex gap-1">
                    <Button size="sm" variant="outline" onClick={() => handleAction(alert.id, 'acknowledge')}>
                      {t('pr.acknowledge')}
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => handleAction(alert.id, 'resolve')}>
                      {t('pr.resolve')}
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => handleAction(alert.id, 'dismiss')}>
                      {t('pr.dismiss')}
                    </Button>
                  </div>
                )}
                {alert.status === 'acknowledged' && (
                  <Button size="sm" variant="outline" onClick={() => handleAction(alert.id, 'resolve')}>
                    {t('pr.resolve')}
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
