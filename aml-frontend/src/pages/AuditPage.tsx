import { useEffect, useState } from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import api from '@/services/api';
import { Search, Shield, CheckCircle, XCircle, Download, RefreshCw } from 'lucide-react';

interface AuditLog {
  id: string;
  user_id: string;
  action: string;
  resource_type: string;
  resource_id: string | null;
  details: Record<string, unknown> | null;
  ip_address: string | null;
  hash: string;
  previous_hash: string | null;
  created_at: string;
}

interface ChainVerification {
  valid: boolean;
  total_records: number;
  verified_records: number;
  broken_at: number | null;
}

export default function AuditPage() {
  const { t } = useLanguage();
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [actionFilter, setActionFilter] = useState('');
  const [chainStatus, setChainStatus] = useState<ChainVerification | null>(null);
  const [verifying, setVerifying] = useState(false);

  const loadLogs = () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (actionFilter) params.set('action', actionFilter);
    api.get(`/api/audit/logs?${params}&limit=100`).then(res => {
      setLogs(Array.isArray(res.data) ? res.data : []);
    }).catch(() => setLogs([])).finally(() => setLoading(false));
  };

  useEffect(() => { loadLogs(); }, [actionFilter]);

  const verifyChain = async () => {
    setVerifying(true);
    try {
      const res = await api.get('/api/audit/verify-chain');
      setChainStatus(res.data);
    } catch {
      setChainStatus({ valid: false, total_records: 0, verified_records: 0, broken_at: null });
    } finally {
      setVerifying(false);
    }
  };

  const exportLogs = () => {
    const csv = [
      'Timestamp,Action,Resource Type,Resource ID,User ID,IP Address,Hash',
      ...logs.map(l => `${l.created_at},${l.action},${l.resource_type},${l.resource_id || ''},${l.user_id},${l.ip_address || ''},${l.hash}`)
    ].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `audit_log_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const actionColors: Record<string, string> = {
    create: 'success', update: 'info', delete: 'danger', login: 'secondary',
    review: 'warning', decide: 'info', override: 'warning', screen: 'info',
  };

  const filtered = logs.filter(l =>
    l.action.toLowerCase().includes(search.toLowerCase()) ||
    l.resource_type.toLowerCase().includes(search.toLowerCase()) ||
    (l.resource_id || '').toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{t('audit.title')}</h1>
          <p className="text-slate-500 text-sm">Immutable Audit Trail & Chain Verification</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={exportLogs}>
            <Download size={16} className="me-2" /> {t('audit.export')}
          </Button>
          <Button onClick={verifyChain} disabled={verifying} className="bg-blue-600 hover:bg-blue-700">
            <Shield size={16} className="me-2" /> {verifying ? 'Verifying...' : t('audit.verify_chain')}
          </Button>
        </div>
      </div>

      {/* Chain Verification Status */}
      {chainStatus && (
        <Card className={chainStatus.valid ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'}>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              {chainStatus.valid ? (
                <CheckCircle className="text-green-600" size={24} />
              ) : (
                <XCircle className="text-red-600" size={24} />
              )}
              <div>
                <p className={`font-medium ${chainStatus.valid ? 'text-green-900' : 'text-red-900'}`}>
                  {chainStatus.valid ? 'Audit Chain Integrity Verified' : 'Audit Chain Integrity BROKEN'}
                </p>
                <p className={`text-sm ${chainStatus.valid ? 'text-green-700' : 'text-red-700'}`}>
                  {chainStatus.verified_records} of {chainStatus.total_records} records verified
                  {chainStatus.broken_at !== null && ` — chain broken at record #${chainStatus.broken_at}`}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Filters */}
      <div className="flex gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
          <Input placeholder={t('common.search')} value={search} onChange={e => setSearch(e.target.value)} className="ps-9" />
        </div>
        <Select value={actionFilter} onChange={e => setActionFilter(e.target.value)} className="w-48">
          <option value="">All Actions</option>
          <option value="create">Create</option>
          <option value="update">Update</option>
          <option value="delete">Delete</option>
          <option value="login">Login</option>
          <option value="review">Review</option>
          <option value="decide">Decide</option>
          <option value="override">Override</option>
          <option value="screen">Screen</option>
        </Select>
        <Button variant="outline" onClick={loadLogs}>
          <RefreshCw size={16} />
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4 text-center">
            <p className="text-sm text-slate-500">Total Records</p>
            <p className="text-3xl font-bold">{logs.length}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <p className="text-sm text-slate-500">Today</p>
            <p className="text-3xl font-bold text-blue-600">
              {logs.filter(l => new Date(l.created_at).toDateString() === new Date().toDateString()).length}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <p className="text-sm text-slate-500">Decisions</p>
            <p className="text-3xl font-bold text-purple-600">
              {logs.filter(l => ['decide', 'review', 'override'].includes(l.action)).length}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <p className="text-sm text-slate-500">Data Access</p>
            <p className="text-3xl font-bold text-amber-600">
              {logs.filter(l => l.action === 'read' || l.action === 'export').length}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Audit Log Table */}
      {loading ? (
        <p className="text-slate-500">{t('common.loading')}</p>
      ) : filtered.length === 0 ? (
        <Card><CardContent className="p-8 text-center text-slate-500">{t('common.no_data')}</CardContent></Card>
      ) : (
        <div className="bg-white rounded-xl border shadow overflow-hidden">
          <table className="w-full">
            <thead className="bg-slate-50 border-b">
              <tr>
                <th className="text-start p-3 text-sm font-medium text-slate-600">Timestamp</th>
                <th className="text-start p-3 text-sm font-medium text-slate-600">Action</th>
                <th className="text-start p-3 text-sm font-medium text-slate-600">Resource</th>
                <th className="text-start p-3 text-sm font-medium text-slate-600">User</th>
                <th className="text-start p-3 text-sm font-medium text-slate-600">IP</th>
                <th className="text-start p-3 text-sm font-medium text-slate-600">{t('audit.hash')}</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(log => (
                <tr key={log.id} className="border-b hover:bg-slate-50 transition-colors">
                  <td className="p-3 text-sm text-slate-500 whitespace-nowrap">
                    {new Date(log.created_at).toLocaleString()}
                  </td>
                  <td className="p-3">
                    <Badge variant={(actionColors[log.action] || 'secondary') as "success" | "info" | "danger" | "secondary" | "warning"}>
                      {log.action}
                    </Badge>
                  </td>
                  <td className="p-3">
                    <span className="text-sm font-medium capitalize">{log.resource_type}</span>
                    {log.resource_id && (
                      <span className="text-xs text-slate-400 ms-2 font-mono">{log.resource_id.slice(0, 8)}...</span>
                    )}
                  </td>
                  <td className="p-3 text-sm font-mono text-slate-500">{log.user_id.slice(0, 8)}...</td>
                  <td className="p-3 text-sm text-slate-500">{log.ip_address || '-'}</td>
                  <td className="p-3">
                    <div className="flex items-center gap-1">
                      <span className="text-xs font-mono text-slate-400">{log.hash.slice(0, 12)}...</span>
                      {log.previous_hash && (
                        <span className="text-xs text-slate-300" title={`Previous: ${log.previous_hash}`}>🔗</span>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
