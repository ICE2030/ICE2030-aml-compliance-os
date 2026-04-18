import { useEffect, useState } from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Select } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import api from '@/services/api';
import { ArrowUpDown, AlertTriangle, Eye, X } from 'lucide-react';

interface TransactionAlert {
  id: string;
  transaction_id: string;
  rule_id: string | null;
  alert_type: string;
  severity: string;
  status: string;
  description: string;
  assigned_to: string | null;
  resolved_by: string | null;
  resolution_notes: string | null;
  created_at: string;
}

interface Transaction {
  id: string;
  entity_id: string;
  transaction_type: string;
  amount: number;
  currency: string;
  counterparty_name: string | null;
  counterparty_country: string | null;
  status: string;
  risk_flags: string[];
  created_at: string;
}

const severityColors: Record<string, string> = {
  low: 'secondary', medium: 'warning', high: 'danger', critical: 'destructive',
};
const alertStatusColors: Record<string, string> = {
  new: 'info', under_review: 'warning', escalated: 'danger',
  dismissed: 'secondary', resolved: 'success',
};

export default function TransactionsPage() {
  const { t } = useLanguage();
  const [alerts, setAlerts] = useState<TransactionAlert[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'alerts' | 'transactions'>('alerts');
  const [selectedAlert, setSelectedAlert] = useState<TransactionAlert | null>(null);
  const [statusFilter, setStatusFilter] = useState('');

  const loadData = () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (statusFilter) params.set('status', statusFilter);
    Promise.all([
      api.get(`/api/transactions/alerts?${params}`).catch(() => ({ data: [] })),
      api.get('/api/transactions/').catch(() => ({ data: [] })),
    ]).then(([alertsRes, txRes]) => {
      setAlerts(Array.isArray(alertsRes.data) ? alertsRes.data : []);
      setTransactions(Array.isArray(txRes.data) ? txRes.data : []);
    }).finally(() => setLoading(false));
  };

  useEffect(() => { loadData(); }, [statusFilter]);

  const resolveAlert = async (alertId: string, status: string, notes: string) => {
    try {
      await api.post(`/api/transactions/alerts/${alertId}/resolve`, {
        status, resolution_notes: notes,
      });
      setSelectedAlert(null);
      loadData();
    } catch (err) { console.error(err); }
  };

  const formatAmount = (amount: number, currency: string) => {
    return new Intl.NumberFormat('en-SA', { style: 'currency', currency: currency || 'SAR' }).format(amount);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{t('transaction.title')}</h1>
          <p className="text-slate-500 text-sm">Rule-based Alerts & Anomaly Detection</p>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4 text-center">
            <p className="text-sm text-slate-500">Total Alerts</p>
            <p className="text-3xl font-bold text-blue-600">{alerts.length}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <p className="text-sm text-slate-500">New</p>
            <p className="text-3xl font-bold text-amber-600">{alerts.filter(a => a.status === 'new').length}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <p className="text-sm text-slate-500">Under Review</p>
            <p className="text-3xl font-bold text-purple-600">{alerts.filter(a => a.status === 'under_review').length}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <p className="text-sm text-slate-500">Resolved</p>
            <p className="text-3xl font-bold text-green-600">{alerts.filter(a => a.status === 'resolved').length}</p>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b pb-2">
        <Button variant={tab === 'alerts' ? 'default' : 'ghost'} onClick={() => setTab('alerts')}>
          <AlertTriangle size={16} className="me-2" /> Alerts ({alerts.length})
        </Button>
        <Button variant={tab === 'transactions' ? 'default' : 'ghost'} onClick={() => setTab('transactions')}>
          <ArrowUpDown size={16} className="me-2" /> Transactions ({transactions.length})
        </Button>
      </div>

      {/* Filter */}
      {tab === 'alerts' && (
        <div className="flex gap-3">
          <Select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} className="w-48">
            <option value="">All Statuses</option>
            <option value="new">New</option>
            <option value="under_review">Under Review</option>
            <option value="escalated">Escalated</option>
            <option value="dismissed">Dismissed</option>
            <option value="resolved">Resolved</option>
          </Select>
        </div>
      )}

      {/* Alert Detail Modal */}
      {selectedAlert && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <Card className="w-full max-w-lg">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>Alert Details</CardTitle>
              <Button variant="ghost" size="icon" onClick={() => setSelectedAlert(null)}><X size={18} /></Button>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="bg-slate-50 rounded-lg p-4 space-y-2">
                <p className="text-sm"><strong>Type:</strong> {selectedAlert.alert_type}</p>
                <p className="text-sm"><strong>Severity:</strong> <Badge variant={(severityColors[selectedAlert.severity] || 'secondary') as "warning" | "danger" | "destructive" | "secondary"}>{selectedAlert.severity}</Badge></p>
                <p className="text-sm"><strong>Description:</strong> {selectedAlert.description}</p>
                <p className="text-sm"><strong>Created:</strong> {new Date(selectedAlert.created_at).toLocaleString()}</p>
              </div>
              {selectedAlert.status === 'new' || selectedAlert.status === 'under_review' ? (
                <div className="space-y-3">
                  <h4 className="font-medium">Resolve Alert</h4>
                  <div className="flex gap-2">
                    <Button variant="success" onClick={() => resolveAlert(selectedAlert.id, 'resolved', 'Alert investigated and resolved - no suspicious activity confirmed')}>
                      Resolve
                    </Button>
                    <Button variant="destructive" onClick={() => resolveAlert(selectedAlert.id, 'escalated', 'Alert escalated for further investigation')}>
                      Escalate
                    </Button>
                    <Button variant="secondary" onClick={() => resolveAlert(selectedAlert.id, 'dismissed', 'Alert dismissed - false positive')}>
                      Dismiss
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="bg-green-50 border border-green-200 rounded-lg p-3">
                  <p className="text-sm text-green-800"><strong>Status:</strong> {selectedAlert.status}</p>
                  {selectedAlert.resolution_notes && <p className="text-sm text-green-700 mt-1">{selectedAlert.resolution_notes}</p>}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* Alerts Table */}
      {tab === 'alerts' && (
        loading ? <p className="text-slate-500">{t('common.loading')}</p> :
        alerts.length === 0 ? (
          <Card><CardContent className="p-8 text-center text-slate-500">{t('common.no_data')}</CardContent></Card>
        ) : (
          <div className="bg-white rounded-xl border shadow overflow-hidden">
            <table className="w-full">
              <thead className="bg-slate-50 border-b">
                <tr>
                  <th className="text-start p-3 text-sm font-medium text-slate-600">Type</th>
                  <th className="text-start p-3 text-sm font-medium text-slate-600">Severity</th>
                  <th className="text-start p-3 text-sm font-medium text-slate-600">Description</th>
                  <th className="text-start p-3 text-sm font-medium text-slate-600">Status</th>
                  <th className="text-start p-3 text-sm font-medium text-slate-600">Created</th>
                  <th className="text-start p-3 text-sm font-medium text-slate-600">{t('common.actions')}</th>
                </tr>
              </thead>
              <tbody>
                {alerts.map(alert => (
                  <tr key={alert.id} className="border-b hover:bg-slate-50 transition-colors">
                    <td className="p-3 text-sm capitalize">{alert.alert_type.replace('_', ' ')}</td>
                    <td className="p-3">
                      <Badge variant={(severityColors[alert.severity] || 'secondary') as "warning" | "danger" | "destructive" | "secondary"}>
                        {alert.severity}
                      </Badge>
                    </td>
                    <td className="p-3 text-sm max-w-xs truncate">{alert.description}</td>
                    <td className="p-3">
                      <Badge variant={(alertStatusColors[alert.status] || 'secondary') as "info" | "warning" | "danger" | "secondary" | "success"}>
                        {alert.status.replace('_', ' ')}
                      </Badge>
                    </td>
                    <td className="p-3 text-sm text-slate-500">{new Date(alert.created_at).toLocaleDateString()}</td>
                    <td className="p-3">
                      <Button size="sm" variant="ghost" onClick={() => setSelectedAlert(alert)}>
                        <Eye size={14} className="me-1" /> View
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}

      {/* Transactions Table */}
      {tab === 'transactions' && (
        loading ? <p className="text-slate-500">{t('common.loading')}</p> :
        transactions.length === 0 ? (
          <Card><CardContent className="p-8 text-center text-slate-500">{t('common.no_data')}</CardContent></Card>
        ) : (
          <div className="bg-white rounded-xl border shadow overflow-hidden">
            <table className="w-full">
              <thead className="bg-slate-50 border-b">
                <tr>
                  <th className="text-start p-3 text-sm font-medium text-slate-600">Type</th>
                  <th className="text-start p-3 text-sm font-medium text-slate-600">Amount</th>
                  <th className="text-start p-3 text-sm font-medium text-slate-600">Counterparty</th>
                  <th className="text-start p-3 text-sm font-medium text-slate-600">Country</th>
                  <th className="text-start p-3 text-sm font-medium text-slate-600">Status</th>
                  <th className="text-start p-3 text-sm font-medium text-slate-600">Risk Flags</th>
                  <th className="text-start p-3 text-sm font-medium text-slate-600">Date</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map(tx => (
                  <tr key={tx.id} className="border-b hover:bg-slate-50 transition-colors">
                    <td className="p-3 text-sm capitalize">{tx.transaction_type}</td>
                    <td className="p-3 text-sm font-medium">{formatAmount(tx.amount, tx.currency)}</td>
                    <td className="p-3 text-sm">{tx.counterparty_name || '-'}</td>
                    <td className="p-3 text-sm">{tx.counterparty_country || '-'}</td>
                    <td className="p-3 text-sm capitalize">{tx.status}</td>
                    <td className="p-3">
                      {tx.risk_flags && tx.risk_flags.length > 0 ? (
                        <div className="flex gap-1 flex-wrap">
                          {tx.risk_flags.map((flag, i) => (
                            <Badge key={i} variant="warning" className="text-xs">{flag}</Badge>
                          ))}
                        </div>
                      ) : '-'}
                    </td>
                    <td className="p-3 text-sm text-slate-500">{new Date(tx.created_at).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}
    </div>
  );
}
