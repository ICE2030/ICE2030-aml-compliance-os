import { useState, useEffect } from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import {
  Zap, Plus, X, CheckCircle, AlertTriangle, Clock, Scan, Link2, Filter,
} from 'lucide-react';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface GRCAction {
  id: string;
  title: string;
  title_ar?: string;
  description?: string;
  reason?: string;
  priority: string;
  status: string;
  source_type: string;
  source_id?: string;
  source_title?: string;
  origin: string;
  owner?: string;
  due_date?: string;
  completed_at?: string;
  created_at?: string;
}

interface ActionSummary {
  total: number;
  open: number;
  overdue: number;
  completed: number;
  by_priority: Record<string, number>;
  by_source: Record<string, number>;
  by_status: Record<string, number>;
  by_origin: Record<string, number>;
}

const PRIORITIES = ['critical', 'high', 'medium', 'low'];
const STATUSES = ['open', 'in_progress', 'completed', 'cancelled', 'overdue'];
const SOURCE_TYPES = ['risk', 'issue', 'audit_finding', 'obligation', 'control', 'evidence', 'pattern', 'alert', 'manual'];
const _ORIGINS = ['manual', 'pattern_generated', 'alert_generated', 'dashboard_generated'];
void _ORIGINS;

export default function ActionCenterPage() {
  const { language } = useLanguage();
  const [actions, setActions] = useState<GRCAction[]>([]);
  const [summary, setSummary] = useState<ActionSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [filterStatus, setFilterStatus] = useState('');
  const [filterPriority, setFilterPriority] = useState('');
  const [filterSource, setFilterSource] = useState('');
  const [crossLinks, setCrossLinks] = useState<Record<string, unknown> | null>(null);
  const [selectedAction, setSelectedAction] = useState<string | null>(null);
  const [form, setForm] = useState({
    title: '', title_ar: '', description: '', description_ar: '', reason: '', reason_ar: '',
    priority: 'medium', source_type: 'manual', owner: '', due_date: '',
  });

  const token = localStorage.getItem('token');
  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  const fetchActions = () => {
    setLoading(true);
    setError(null);
    const params = new URLSearchParams();
    if (filterStatus) params.set('status', filterStatus);
    if (filterPriority) params.set('priority', filterPriority);
    if (filterSource) params.set('source_type', filterSource);
    fetch(`${API}/api/grc/actions?${params}`, { headers })
      .then(r => { if (!r.ok) throw new Error(`API ${r.status}`); return r.json(); })
      .then(data => setActions(data.items || []))
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load actions'))
      .finally(() => setLoading(false));
  };

  const fetchSummary = () => {
    fetch(`${API}/api/grc/actions/summary`, { headers })
      .then(r => { if (!r.ok) throw new Error(`API ${r.status}`); return r.json(); })
      .then(setSummary)
      .catch(() => {});
  };

  useEffect(() => { fetchActions(); fetchSummary(); }, [filterStatus, filterPriority, filterSource]);

  const handleCreate = async () => {
    try {
      const body: Record<string, unknown> = { ...form, origin: 'manual' };
      if (!body.due_date) delete body.due_date;
      const res = await fetch(`${API}/api/grc/actions`, { method: 'POST', headers, body: JSON.stringify(body) });
      if (!res.ok) { setError(`Failed to create action: ${res.status}`); return; }
      setShowCreate(false);
      setForm({ title: '', title_ar: '', description: '', description_ar: '', reason: '', reason_ar: '', priority: 'medium', source_type: 'manual', owner: '', due_date: '' });
      fetchActions();
      fetchSummary();
    } catch (e) { setError(e instanceof Error ? e.message : 'Failed to create action'); }
  };

  const handleComplete = async (id: string) => {
    try {
      const res = await fetch(`${API}/api/grc/actions/${id}`, {
        method: 'PUT', headers, body: JSON.stringify({ status: 'completed' }),
      });
      if (!res.ok) { setError(`Failed to complete action: ${res.status}`); return; }
      fetchActions();
      fetchSummary();
    } catch (e) { setError(e instanceof Error ? e.message : 'Failed to complete action'); }
  };

  const handleDelete = async (id: string) => {
    try {
      const res = await fetch(`${API}/api/grc/actions/${id}`, { method: 'DELETE', headers });
      if (!res.ok) { setError(`Failed to delete action: ${res.status}`); return; }
      fetchActions();
      fetchSummary();
    } catch (e) { setError(e instanceof Error ? e.message : 'Failed to delete action'); }
  };

  const handleScanAlerts = async () => {
    try {
      const res = await fetch(`${API}/api/grc/actions/scan-alerts`, { method: 'POST', headers });
      if (!res.ok) { setError(`Failed to scan alerts: ${res.status}`); return; }
      fetchActions();
      fetchSummary();
    } catch (e) { setError(e instanceof Error ? e.message : 'Failed to scan alerts'); }
  };

  const handleScanPatterns = async () => {
    try {
      const res = await fetch(`${API}/api/grc/actions/scan-patterns`, { method: 'POST', headers });
      if (!res.ok) { setError(`Failed to scan patterns: ${res.status}`); return; }
      fetchActions();
      fetchSummary();
    } catch (e) { setError(e instanceof Error ? e.message : 'Failed to scan patterns'); }
  };

  const handleApprove = async (id: string) => {
    try {
      const res = await fetch(`${API}/api/grc/actions/${id}/approve`, { method: 'POST', headers });
      if (!res.ok) { setError(`Failed to approve action: ${res.status}`); return; }
      fetchActions();
      fetchSummary();
    } catch (e) { setError(e instanceof Error ? e.message : 'Failed to approve action'); }
  };

  const fetchCrossLinks = async (action: GRCAction) => {
    if (selectedAction === action.id) {
      setSelectedAction(null);
      setCrossLinks(null);
      return;
    }
    setSelectedAction(action.id);
    try {
      const res = await fetch(`${API}/api/grc/cross-links/action/${action.id}`, { headers });
      if (res.ok) setCrossLinks(await res.json());
    } catch { setCrossLinks(null); }
  };

  const priorityColor = (p: string) => {
    switch (p) {
      case 'critical': return 'bg-red-100 text-red-800 border-red-300';
      case 'high': return 'bg-orange-100 text-orange-800 border-orange-300';
      case 'medium': return 'bg-yellow-100 text-yellow-800 border-yellow-300';
      case 'low': return 'bg-blue-100 text-blue-800 border-blue-300';
      default: return 'bg-slate-100 text-slate-800';
    }
  };

  const statusColor = (s: string) => {
    switch (s) {
      case 'open': return 'bg-blue-100 text-blue-800';
      case 'in_progress': return 'bg-yellow-100 text-yellow-800';
      case 'completed': return 'bg-green-100 text-green-800';
      case 'cancelled': return 'bg-slate-100 text-slate-600';
      case 'overdue': return 'bg-red-100 text-red-800';
      default: return 'bg-slate-100 text-slate-800';
    }
  };

  const originLabel = (o: string) => {
    switch (o) {
      case 'manual': return language === 'ar' ? 'يدوي' : 'Manual';
      case 'pattern_generated': return language === 'ar' ? 'من نمط' : 'Pattern';
      case 'alert_generated': return language === 'ar' ? 'من تنبيه' : 'Alert';
      case 'dashboard_generated': return language === 'ar' ? 'من لوحة' : 'Dashboard';
      default: return o;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            {language === 'ar' ? 'مركز الإجراءات' : 'Action Center'}
          </h1>
          <p className="text-slate-500 mt-1">
            {language === 'ar' ? 'إجراءات موحدة من جميع مصادر الحوكمة والمخاطر والامتثال' : 'Unified actions from all GRC sources — risks, issues, findings, controls, evidence'}
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleScanAlerts} title={language === 'ar' ? 'فحص التنبيهات' : 'Scan Alerts'}>
            <Scan size={16} className="me-2" />
            {language === 'ar' ? 'فحص التنبيهات' : 'Scan Alerts'}
          </Button>
          <Button variant="outline" onClick={handleScanPatterns} title={language === 'ar' ? 'فحص الأنماط' : 'Scan Patterns'}>
            <Zap size={16} className="me-2" />
            {language === 'ar' ? 'فحص الأنماط' : 'Scan Patterns'}
          </Button>
          <Button onClick={() => setShowCreate(!showCreate)}>
            {showCreate ? <X size={16} className="me-2" /> : <Plus size={16} className="me-2" />}
            {showCreate ? (language === 'ar' ? 'إلغاء' : 'Cancel') : (language === 'ar' ? 'إنشاء إجراء' : 'Create Action')}
          </Button>
        </div>
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

      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card>
            <CardContent className="pt-6 text-center">
              <p className="text-3xl font-bold text-blue-600">{summary.total}</p>
              <p className="text-sm text-slate-500">{language === 'ar' ? 'إجمالي الإجراءات' : 'Total Actions'}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6 text-center">
              <p className="text-3xl font-bold text-orange-600">{summary.open}</p>
              <p className="text-sm text-slate-500">{language === 'ar' ? 'مفتوح' : 'Open'}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6 text-center">
              <p className="text-3xl font-bold text-red-600">{summary.overdue}</p>
              <p className="text-sm text-slate-500">{language === 'ar' ? 'متأخر' : 'Overdue'}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6 text-center">
              <p className="text-3xl font-bold text-green-600">{summary.completed}</p>
              <p className="text-sm text-slate-500">{language === 'ar' ? 'مكتمل' : 'Completed'}</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-3 flex-wrap items-center">
        <Filter size={16} className="text-slate-400" />
        <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)} className="border rounded-md px-3 py-2 text-sm">
          <option value="">{language === 'ar' ? 'كل الحالات' : 'All Statuses'}</option>
          {STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={filterPriority} onChange={e => setFilterPriority(e.target.value)} className="border rounded-md px-3 py-2 text-sm">
          <option value="">{language === 'ar' ? 'كل الأولويات' : 'All Priorities'}</option>
          {PRIORITIES.map(p => <option key={p} value={p}>{p}</option>)}
        </select>
        <select value={filterSource} onChange={e => setFilterSource(e.target.value)} className="border rounded-md px-3 py-2 text-sm">
          <option value="">{language === 'ar' ? 'كل المصادر' : 'All Sources'}</option>
          {SOURCE_TYPES.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {/* Create Form */}
      {showCreate && (
        <Card className="border-blue-200 bg-blue-50/30">
          <CardHeader><CardTitle>{language === 'ar' ? 'إنشاء إجراء جديد' : 'Create New Action'}</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'العنوان (EN)' : 'Title (EN)'}</label>
                <Input value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} placeholder="Action title..." />
              </div>
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'العنوان (AR)' : 'Title (AR)'}</label>
                <Input value={form.title_ar} onChange={e => setForm({ ...form, title_ar: e.target.value })} placeholder="عنوان الإجراء..." dir="rtl" />
              </div>
              <div className="md:col-span-2">
                <label className="text-sm font-medium">{language === 'ar' ? 'الوصف' : 'Description'}</label>
                <textarea className="w-full border rounded-md p-2 text-sm" rows={2} value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} />
              </div>
              <div className="md:col-span-2">
                <label className="text-sm font-medium">{language === 'ar' ? 'السبب' : 'Reason'}</label>
                <textarea className="w-full border rounded-md p-2 text-sm" rows={2} value={form.reason} onChange={e => setForm({ ...form, reason: e.target.value })} />
              </div>
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'الأولوية' : 'Priority'}</label>
                <select className="w-full border rounded-md px-3 py-2 text-sm" value={form.priority} onChange={e => setForm({ ...form, priority: e.target.value })}>
                  {PRIORITIES.map(p => <option key={p} value={p}>{p}</option>)}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'نوع المصدر' : 'Source Type'}</label>
                <select className="w-full border rounded-md px-3 py-2 text-sm" value={form.source_type} onChange={e => setForm({ ...form, source_type: e.target.value })}>
                  {SOURCE_TYPES.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'المالك' : 'Owner'}</label>
                <Input value={form.owner} onChange={e => setForm({ ...form, owner: e.target.value })} placeholder="Action owner..." />
              </div>
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'تاريخ الاستحقاق' : 'Due Date'}</label>
                <Input type="date" value={form.due_date} onChange={e => setForm({ ...form, due_date: e.target.value })} />
              </div>
            </div>
            <Button onClick={handleCreate} disabled={!form.title}>
              {language === 'ar' ? 'إنشاء الإجراء' : 'Create Action'}
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Actions List */}
      {loading ? (
        <div className="flex items-center justify-center h-32"><div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" /></div>
      ) : actions.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <Zap size={48} className="mx-auto text-slate-300 mb-4" />
            <p className="text-slate-500">{language === 'ar' ? 'لا توجد إجراءات بعد' : 'No actions yet'}</p>
            <p className="text-sm text-slate-400 mt-1">
              {language === 'ar' ? 'أنشئ إجراء أو افحص التنبيهات/الأنماط لتوليد إجراءات تلقائياً' : 'Create an action or scan alerts/patterns to auto-generate actions'}
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {actions.map(action => (
            <Card key={action.id} className={`hover:shadow-md transition-shadow ${action.status === 'completed' ? 'opacity-60' : ''}`}>
              <CardContent className="py-4">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <Zap size={16} className="text-blue-500" />
                      <h3 className="font-semibold text-slate-800">
                        {language === 'ar' && action.title_ar ? action.title_ar : action.title}
                      </h3>
                      <Badge className={`text-xs ${priorityColor(action.priority)}`}>{action.priority}</Badge>
                      <Badge className={`text-xs ${statusColor(action.status)}`}>{action.status}</Badge>
                      <Badge variant="outline" className="text-xs">{originLabel(action.origin)}</Badge>
                    </div>
                    {action.description && <p className="text-sm text-slate-500 line-clamp-2 mb-2">{action.description}</p>}
                    {action.reason && <p className="text-xs text-slate-400 italic mb-2">{language === 'ar' ? 'السبب: ' : 'Reason: '}{action.reason}</p>}
                    <div className="flex items-center gap-4 text-xs text-slate-400 flex-wrap">
                      <span>{language === 'ar' ? 'المصدر' : 'Source'}: {action.source_type}{action.source_title ? ` — ${action.source_title}` : ''}</span>
                      {action.owner && <span>{language === 'ar' ? 'المالك' : 'Owner'}: {action.owner}</span>}
                      {action.due_date && (
                        <span className={new Date(action.due_date) < new Date() && action.status !== 'completed' ? 'text-red-500 font-medium' : ''}>
                          <Clock size={12} className="inline me-1" />
                          {language === 'ar' ? 'الاستحقاق' : 'Due'}: {action.due_date.split('T')[0]}
                        </span>
                      )}
                    </div>

                    {/* Cross-links panel */}
                    {selectedAction === action.id && crossLinks && (
                      <div className="mt-3 p-3 bg-slate-50 rounded-lg border text-xs space-y-2">
                        <p className="font-semibold text-slate-700">{language === 'ar' ? 'الروابط المتقاطعة' : 'Cross-Links'}</p>
                        {(['risks', 'issues', 'findings', 'obligations', 'controls', 'evidence'] as const).map(key => {
                          const items = (crossLinks as Record<string, Array<{ id: string; title: string }>>)[key];
                          if (!items || !Array.isArray(items) || items.length === 0) return null;
                          return (
                            <div key={key}>
                              <span className="font-medium text-slate-600 capitalize">{key}:</span>{' '}
                              {items.map((item, i) => (
                                <Badge key={i} variant="outline" className="text-xs me-1 mb-1">{item.title || item.id}</Badge>
                              ))}
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    <Button variant="ghost" size="sm" onClick={() => fetchCrossLinks(action)} title={language === 'ar' ? 'روابط' : 'Links'}>
                      <Link2 size={14} />
                    </Button>
                    {action.status !== 'completed' && (
                      <Button variant="ghost" size="sm" onClick={() => handleComplete(action.id)} className="text-green-600" title={language === 'ar' ? 'إكمال' : 'Complete'}>
                        <CheckCircle size={14} />
                      </Button>
                    )}
                    {action.origin === 'pattern_generated' && action.status === 'open' && (
                      <Button variant="ghost" size="sm" onClick={() => handleApprove(action.id)} className="text-blue-600" title={language === 'ar' ? 'موافقة' : 'Approve'}>
                        <AlertTriangle size={14} />
                      </Button>
                    )}
                    <Button variant="ghost" size="sm" onClick={() => handleDelete(action.id)} className="text-red-500 hover:text-red-700">
                      <X size={14} />
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
