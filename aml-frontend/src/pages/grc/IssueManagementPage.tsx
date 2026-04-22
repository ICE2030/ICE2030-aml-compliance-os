import { useState, useEffect } from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { AlertTriangle, Plus, X, Clock, CheckCircle } from 'lucide-react';
import { EmptyState } from '@/components/EmptyState';
import { trackUsage } from '@/hooks/useUsageTracking';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface GRCIssue {
  id: string;
  title: string;
  title_ar?: string;
  description: string;
  source: string;
  severity: string;
  status: string;
  escalation_status: string;
  owner?: string;
  due_date?: string;
  closed_at?: string;
  aging_days: number;
  created_at?: string;
}

const SOURCES = ['audit', 'risk', 'compliance', 'incident', 'management_review', 'regulator_note'];
const SEVERITIES = ['low', 'medium', 'high', 'critical'];
const STATUSES = ['open', 'in_progress', 'pending_closure', 'closed', 'overdue', 'escalated'];

export default function IssueManagementPage() {
  const { language, t } = useLanguage();
  const [issues, setIssues] = useState<GRCIssue[]>([]);
  const [summary, setSummary] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [filterSource, setFilterSource] = useState('');
  const [filterSeverity, setFilterSeverity] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [form, setForm] = useState({
    title: '', title_ar: '', description: '', description_ar: '',
    source: 'compliance', severity: 'medium', owner: '', due_date: '',
  });

  const token = localStorage.getItem('token');
  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  const fetchData = () => {
    setLoading(true);
    setError(null);
    const params = new URLSearchParams();
    if (filterSource) params.set('source', filterSource);
    if (filterSeverity) params.set('severity', filterSeverity);
    if (filterStatus) params.set('status', filterStatus);

    Promise.all([
      fetch(`${API}/api/grc/issues?${params}`, { headers }).then(r => { if (!r.ok) throw new Error(`API ${r.status}`); return r.json(); }),
      fetch(`${API}/api/grc/issues/summary`, { headers }).then(r => { if (!r.ok) throw new Error(`API ${r.status}`); return r.json(); }),
    ]).then(([issuesData, summaryData]) => {
      setIssues(issuesData.items || []);
      setSummary(summaryData);
    }).catch((e) => setError(e instanceof Error ? e.message : 'Failed to load issues')).finally(() => setLoading(false));
  };

  useEffect(() => { fetchData(); }, [filterSource, filterSeverity, filterStatus]);

  const handleCreate = async () => {
    try {
      const body: Record<string, unknown> = { ...form };
      if (!body.due_date) delete body.due_date;
      const res = await fetch(`${API}/api/grc/issues`, { method: 'POST', headers, body: JSON.stringify(body) });
      if (!res.ok) { setError(`Failed to create issue: ${res.status}`); return; }
      const created = await res.json().catch(() => ({}));
      trackUsage('create', { resource_type: 'issue', resource_id: created.id, path: '/grc/issues' });
      setShowCreate(false);
      setForm({ title: '', title_ar: '', description: '', description_ar: '', source: 'compliance', severity: 'medium', owner: '', due_date: '' });
      fetchData();
    } catch (e) { setError(e instanceof Error ? e.message : 'Failed to create issue'); }
  };

  const handleStatusChange = async (id: string, newStatus: string) => {
    try {
      const res = await fetch(`${API}/api/grc/issues/${id}`, { method: 'PUT', headers, body: JSON.stringify({ status: newStatus }) });
      if (!res.ok) { setError(`Failed to update issue: ${res.status}`); return; }
      trackUsage('update', { resource_type: 'issue', resource_id: id, path: '/grc/issues', metadata: { status: newStatus } });
      fetchData();
    } catch (e) { setError(e instanceof Error ? e.message : 'Failed to update issue'); }
  };

  const handleDelete = async (id: string) => {
    try {
      const res = await fetch(`${API}/api/grc/issues/${id}`, { method: 'DELETE', headers });
      if (!res.ok) { setError(`Failed to delete issue: ${res.status}`); return; }
      trackUsage('delete', { resource_type: 'issue', resource_id: id, path: '/grc/issues' });
      fetchData();
    } catch (e) { setError(e instanceof Error ? e.message : 'Failed to delete issue'); }
  };

  const severityColor = (s: string) => {
    switch (s) {
      case 'critical': return 'bg-red-100 text-red-800';
      case 'high': return 'bg-orange-100 text-orange-800';
      case 'medium': return 'bg-yellow-100 text-yellow-800';
      default: return 'bg-green-100 text-green-800';
    }
  };

  const statusColor = (s: string) => {
    switch (s) {
      case 'closed': return 'bg-green-100 text-green-800';
      case 'in_progress': return 'bg-blue-100 text-blue-800';
      case 'overdue': case 'escalated': return 'bg-red-100 text-red-800';
      default: return 'bg-slate-100 text-slate-800';
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            {language === 'ar' ? 'إدارة المشاكل' : 'Issue Management'}
          </h1>
          <p className="text-slate-500 mt-1">
            {language === 'ar' ? 'تتبع المشاكل من التدقيق والمخاطر والامتثال والحوادث' : 'Track issues from audit, risk, compliance, and incidents'}
          </p>
        </div>
        <Button onClick={() => setShowCreate(!showCreate)}>
          {showCreate ? <X size={16} className="me-2" /> : <Plus size={16} className="me-2" />}
          {showCreate ? (language === 'ar' ? 'إلغاء' : 'Cancel') : (language === 'ar' ? 'إضافة مشكلة' : 'Add Issue')}
        </Button>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle size={16} className="text-red-500" />
            <span className="text-sm text-red-700">{error}</span>
          </div>
          <Button variant="ghost" size="sm" onClick={() => setError(null)}><X size={14} /></Button>
        </div>
      )}

      {/* Summary */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card><CardContent className="pt-4 text-center">
            <p className="text-sm text-slate-500">{language === 'ar' ? 'الإجمالي' : 'Total'}</p>
            <p className="text-2xl font-bold">{(summary as { total?: number }).total || 0}</p>
          </CardContent></Card>
          <Card><CardContent className="pt-4 text-center">
            <p className="text-sm text-slate-500">{language === 'ar' ? 'مفتوحة' : 'Open'}</p>
            <p className="text-2xl font-bold text-orange-600">{(summary as { open?: number }).open || 0}</p>
          </CardContent></Card>
          <Card><CardContent className="pt-4 text-center">
            <p className="text-sm text-slate-500">{language === 'ar' ? 'حرجة مفتوحة' : 'Critical Open'}</p>
            <p className="text-2xl font-bold text-red-600">{(summary as { critical_open?: number }).critical_open || 0}</p>
          </CardContent></Card>
          <Card><CardContent className="pt-4 text-center">
            <p className="text-sm text-slate-500">{language === 'ar' ? 'متأخرة' : 'Overdue'}</p>
            <p className="text-2xl font-bold text-red-600">{(summary as { overdue?: number }).overdue || 0}</p>
          </CardContent></Card>
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-3 flex-wrap">
        <select value={filterSource} onChange={e => setFilterSource(e.target.value)} className="border rounded-md px-3 py-2 text-sm">
          <option value="">{language === 'ar' ? 'كل المصادر' : 'All Sources'}</option>
          {SOURCES.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={filterSeverity} onChange={e => setFilterSeverity(e.target.value)} className="border rounded-md px-3 py-2 text-sm">
          <option value="">{language === 'ar' ? 'كل الخطورات' : 'All Severities'}</option>
          {SEVERITIES.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)} className="border rounded-md px-3 py-2 text-sm">
          <option value="">{language === 'ar' ? 'كل الحالات' : 'All Statuses'}</option>
          {STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {/* Create Form */}
      {showCreate && (
        <Card className="border-blue-200 bg-blue-50/30">
          <CardHeader><CardTitle>{language === 'ar' ? 'إضافة مشكلة جديدة' : 'Add New Issue'}</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'العنوان (EN)' : 'Title (EN)'}</label>
                <Input value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} placeholder="Issue title..." />
              </div>
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'العنوان (AR)' : 'Title (AR)'}</label>
                <Input value={form.title_ar} onChange={e => setForm({ ...form, title_ar: e.target.value })} placeholder="عنوان المشكلة..." dir="rtl" />
              </div>
              <div className="md:col-span-2">
                <label className="text-sm font-medium">{language === 'ar' ? 'الوصف' : 'Description'}</label>
                <textarea className="w-full border rounded-md p-2 text-sm" rows={2} value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} />
              </div>
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'المصدر' : 'Source'}</label>
                <select className="w-full border rounded-md px-3 py-2 text-sm" value={form.source} onChange={e => setForm({ ...form, source: e.target.value })}>
                  {SOURCES.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'الخطورة' : 'Severity'}</label>
                <select className="w-full border rounded-md px-3 py-2 text-sm" value={form.severity} onChange={e => setForm({ ...form, severity: e.target.value })}>
                  {SEVERITIES.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'المالك' : 'Owner'}</label>
                <Input value={form.owner} onChange={e => setForm({ ...form, owner: e.target.value })} placeholder="Issue owner..." />
              </div>
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'تاريخ الاستحقاق' : 'Due Date'}</label>
                <Input type="date" value={form.due_date} onChange={e => setForm({ ...form, due_date: e.target.value })} />
              </div>
            </div>
            <Button onClick={handleCreate} disabled={!form.title || !form.description}>
              {language === 'ar' ? 'إنشاء المشكلة' : 'Create Issue'}
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Issue List */}
      {loading ? (
        <div className="flex items-center justify-center h-32"><div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" /></div>
      ) : issues.length === 0 ? (
        <EmptyState
          icon={<AlertTriangle size={48} />}
          title={t('empty.issues_title')}
          hint={t('empty.issues_hint')}
          primaryAction={
            <Button onClick={() => setShowCreate(true)}>
              <Plus size={16} className="me-2" />
              {language === 'ar' ? 'إضافة مشكلة' : 'Add Issue'}
            </Button>
          }
          showLoadSamples
          onSamplesLoaded={fetchData}
        />
      ) : (
        <div className="space-y-3">
          {issues.map(issue => (
            <Card key={issue.id} className="hover:shadow-md transition-shadow">
              <CardContent className="py-4">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <h3 className="font-semibold text-slate-800">
                        {language === 'ar' && issue.title_ar ? issue.title_ar : issue.title}
                      </h3>
                      <Badge className={`text-xs ${severityColor(issue.severity)}`}>{issue.severity}</Badge>
                      <Badge className={`text-xs ${statusColor(issue.status)}`}>{issue.status}</Badge>
                      <Badge variant="outline" className="text-xs">{issue.source}</Badge>
                    </div>
                    <p className="text-sm text-slate-500 line-clamp-1 mb-2">{issue.description}</p>
                    <div className="flex items-center gap-4 text-xs text-slate-400">
                      <span className="flex items-center gap-1"><Clock size={12} /> {issue.aging_days} {language === 'ar' ? 'يوم' : 'days'}</span>
                      {issue.owner && <span>{language === 'ar' ? 'المالك' : 'Owner'}: {issue.owner}</span>}
                      {issue.due_date && <span>{language === 'ar' ? 'الاستحقاق' : 'Due'}: {new Date(issue.due_date).toLocaleDateString()}</span>}
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    {issue.status !== 'closed' && (
                      <Button variant="ghost" size="sm" onClick={() => handleStatusChange(issue.id, 'closed')} className="text-green-600 hover:text-green-800" title="Close">
                        <CheckCircle size={16} />
                      </Button>
                    )}
                    <Button variant="ghost" size="sm" onClick={() => handleDelete(issue.id)} className="text-red-500 hover:text-red-700">
                      <X size={16} />
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
