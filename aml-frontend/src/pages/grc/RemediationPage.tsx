import { useState, useEffect } from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Wrench, Plus, X, CheckCircle, AlertCircle, Clock } from 'lucide-react';
import { EmptyState } from '@/components/EmptyState';
import { trackUsage } from '@/hooks/useUsageTracking';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface Action {
  id: string;
  issue_id: string;
  title: string;
  title_ar?: string;
  description: string;
  owner?: string;
  target_date?: string;
  completed_at?: string;
  status: string;
  progress_pct: number;
  blockers?: string;
  created_at?: string;
}

interface Milestone {
  id: string;
  action_id: string;
  title: string;
  title_ar?: string;
  target_date?: string;
  is_completed: boolean;
  notes?: string;
}

export default function RemediationPage() {
  const { language, t } = useLanguage();
  const [actions, setActions] = useState<Action[]>([]);
  const [summary, setSummary] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [expandedAction, setExpandedAction] = useState<string | null>(null);
  const [milestones, setMilestones] = useState<Record<string, Milestone[]>>({});
  const [milestoneForm, setMilestoneForm] = useState({ title: '', target_date: '' });
  const [form, setForm] = useState({
    issue_id: '', title: '', title_ar: '', description: '', description_ar: '',
    owner: '', target_date: '',
  });

  const token = localStorage.getItem('token');
  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  const fetchData = () => {
    setLoading(true);
    Promise.all([
      fetch(`${API}/api/grc/remediation`, { headers }).then(r => r.json()),
      fetch(`${API}/api/grc/remediation/summary`, { headers }).then(r => r.json()),
    ]).then(([actionsData, summaryData]) => {
      setActions(actionsData.items || []);
      setSummary(summaryData);
    }).catch(() => {}).finally(() => setLoading(false));
  };

  useEffect(() => { fetchData(); }, []);

  const handleCreate = async () => {
    const body: Record<string, unknown> = { ...form };
    if (!body.target_date) delete body.target_date;
    const res = await fetch(`${API}/api/grc/remediation`, { method: 'POST', headers, body: JSON.stringify(body) });
    if (res.ok) {
      const created = await res.json().catch(() => ({} as { id?: string }));
      trackUsage('create', { resource_type: 'remediation_action', resource_id: created?.id, path: '/grc/remediation' });
      setShowCreate(false);
      setForm({ issue_id: '', title: '', title_ar: '', description: '', description_ar: '', owner: '', target_date: '' });
      fetchData();
    }
  };

  const handleUpdateStatus = async (id: string, status: string, progress_pct?: number) => {
    const body: Record<string, unknown> = { status };
    if (progress_pct !== undefined) body.progress_pct = progress_pct;
    await fetch(`${API}/api/grc/remediation/${id}`, { method: 'PUT', headers, body: JSON.stringify(body) });
    trackUsage('update', { resource_type: 'remediation_action', resource_id: id, path: '/grc/remediation', metadata: { status } });
    fetchData();
  };

  const handleDelete = async (id: string) => {
    await fetch(`${API}/api/grc/remediation/${id}`, { method: 'DELETE', headers });
    trackUsage('delete', { resource_type: 'remediation_action', resource_id: id, path: '/grc/remediation' });
    fetchData();
  };

  const fetchMilestones = async (actionId: string) => {
    const res = await fetch(`${API}/api/grc/remediation/${actionId}/milestones`, { headers });
    const data = await res.json();
    setMilestones(prev => ({ ...prev, [actionId]: data }));
  };

  const handleToggleExpand = async (actionId: string) => {
    if (expandedAction === actionId) {
      setExpandedAction(null);
    } else {
      setExpandedAction(actionId);
      await fetchMilestones(actionId);
    }
  };

  const handleCreateMilestone = async (actionId: string) => {
    const body: Record<string, unknown> = { title: milestoneForm.title };
    if (milestoneForm.target_date) body.target_date = milestoneForm.target_date;
    await fetch(`${API}/api/grc/remediation/${actionId}/milestones`, { method: 'POST', headers, body: JSON.stringify(body) });
    setMilestoneForm({ title: '', target_date: '' });
    await fetchMilestones(actionId);
  };

  const handleToggleMilestone = async (milestoneId: string, completed: boolean, actionId: string) => {
    await fetch(`${API}/api/grc/remediation/milestones/${milestoneId}`, { method: 'PUT', headers, body: JSON.stringify({ is_completed: !completed }) });
    await fetchMilestones(actionId);
  };

  const statusColor = (s: string) => {
    switch (s) {
      case 'completed': case 'verified': return 'bg-green-100 text-green-800';
      case 'in_progress': return 'bg-blue-100 text-blue-800';
      case 'blocked': return 'bg-red-100 text-red-800';
      default: return 'bg-slate-100 text-slate-800';
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            {language === 'ar' ? 'تتبع الإجراءات العلاجية' : 'Remediation Tracking'}
          </h1>
          <p className="text-slate-500 mt-1">
            {language === 'ar' ? 'خطط العمل والمعالم والتقدم والإغلاق' : 'Action plans, milestones, progress, and closure'}
          </p>
        </div>
        <Button onClick={() => setShowCreate(!showCreate)}>
          {showCreate ? <X size={16} className="me-2" /> : <Plus size={16} className="me-2" />}
          {showCreate ? (language === 'ar' ? 'إلغاء' : 'Cancel') : (language === 'ar' ? 'إضافة إجراء' : 'Add Action')}
        </Button>
      </div>

      {/* Summary */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <Card><CardContent className="pt-4 text-center">
            <p className="text-sm text-slate-500">{language === 'ar' ? 'الإجمالي' : 'Total'}</p>
            <p className="text-2xl font-bold">{(summary as { total?: number }).total || 0}</p>
          </CardContent></Card>
          <Card><CardContent className="pt-4 text-center">
            <p className="text-sm text-slate-500">{language === 'ar' ? 'قيد التنفيذ' : 'In Progress'}</p>
            <p className="text-2xl font-bold text-blue-600">{(summary as { in_progress?: number }).in_progress || 0}</p>
          </CardContent></Card>
          <Card><CardContent className="pt-4 text-center">
            <p className="text-sm text-slate-500">{language === 'ar' ? 'مكتمل' : 'Completed'}</p>
            <p className="text-2xl font-bold text-green-600">{(summary as { completed?: number }).completed || 0}</p>
          </CardContent></Card>
          <Card><CardContent className="pt-4 text-center">
            <p className="text-sm text-slate-500">{language === 'ar' ? 'محظور' : 'Blocked'}</p>
            <p className="text-2xl font-bold text-red-600">{(summary as { blocked?: number }).blocked || 0}</p>
          </CardContent></Card>
          <Card><CardContent className="pt-4 text-center">
            <p className="text-sm text-slate-500">{language === 'ar' ? 'متوسط التقدم' : 'Avg Progress'}</p>
            <p className="text-2xl font-bold">{(summary as { avg_progress_pct?: number }).avg_progress_pct || 0}%</p>
          </CardContent></Card>
        </div>
      )}

      {/* Create Form */}
      {showCreate && (
        <Card className="border-blue-200 bg-blue-50/30">
          <CardHeader><CardTitle>{language === 'ar' ? 'إضافة إجراء علاجي جديد' : 'Add New Remediation Action'}</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'معرّف المشكلة' : 'Issue ID'}</label>
                <Input value={form.issue_id} onChange={e => setForm({ ...form, issue_id: e.target.value })} placeholder="Issue ID (from issue management)..." />
              </div>
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'العنوان' : 'Title'}</label>
                <Input value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} placeholder="Action title..." />
              </div>
              <div className="md:col-span-2">
                <label className="text-sm font-medium">{language === 'ar' ? 'الوصف' : 'Description'}</label>
                <textarea className="w-full border rounded-md p-2 text-sm" rows={2} value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} />
              </div>
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'المالك' : 'Owner'}</label>
                <Input value={form.owner} onChange={e => setForm({ ...form, owner: e.target.value })} placeholder="Action owner..." />
              </div>
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'التاريخ المستهدف' : 'Target Date'}</label>
                <Input type="date" value={form.target_date} onChange={e => setForm({ ...form, target_date: e.target.value })} />
              </div>
            </div>
            <Button onClick={handleCreate} disabled={!form.issue_id || !form.title || !form.description}>
              {language === 'ar' ? 'إنشاء الإجراء' : 'Create Action'}
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Actions List */}
      {loading ? (
        <div className="flex items-center justify-center h-32"><div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" /></div>
      ) : actions.length === 0 ? (
        <EmptyState
          icon={<Wrench size={48} />}
          title={t('empty.remediations_title')}
          hint={t('empty.remediations_hint')}
          primaryAction={
            <Button onClick={() => setShowCreate(true)}>
              <Plus size={16} className="me-2" />
              {language === 'ar' ? 'إضافة إجراء' : 'Add Action'}
            </Button>
          }
          showLoadSamples
          onSamplesLoaded={fetchData}
        />
      ) : (
        <div className="space-y-3">
          {actions.map(action => (
            <Card key={action.id} className="hover:shadow-md transition-shadow">
              <CardContent className="py-4">
                <div className="flex items-start justify-between">
                  <div className="flex-1 cursor-pointer" onClick={() => handleToggleExpand(action.id)}>
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <h3 className="font-semibold text-slate-800">
                        {language === 'ar' && action.title_ar ? action.title_ar : action.title}
                      </h3>
                      <Badge className={`text-xs ${statusColor(action.status)}`}>{action.status}</Badge>
                    </div>
                    <p className="text-sm text-slate-500 line-clamp-1 mb-2">{action.description}</p>
                    {/* Progress bar */}
                    <div className="flex items-center gap-3 mb-2">
                      <div className="flex-1 bg-slate-200 rounded-full h-2">
                        <div className={`h-2 rounded-full ${action.progress_pct >= 100 ? 'bg-green-500' : action.progress_pct >= 50 ? 'bg-blue-500' : 'bg-orange-500'}`} style={{ width: `${action.progress_pct}%` }} />
                      </div>
                      <span className="text-xs font-medium text-slate-600">{action.progress_pct}%</span>
                    </div>
                    <div className="flex items-center gap-4 text-xs text-slate-400">
                      {action.owner && <span>{language === 'ar' ? 'المالك' : 'Owner'}: {action.owner}</span>}
                      {action.target_date && <span className="flex items-center gap-1"><Clock size={12} /> {new Date(action.target_date).toLocaleDateString()}</span>}
                      {action.blockers && <span className="flex items-center gap-1 text-red-500"><AlertCircle size={12} /> {language === 'ar' ? 'عوائق' : 'Blocked'}</span>}
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    {action.status !== 'completed' && action.status !== 'verified' && (
                      <>
                        <Button variant="ghost" size="sm" onClick={() => handleUpdateStatus(action.id, 'in_progress', Math.min(100, action.progress_pct + 25))} className="text-blue-600" title="Progress +25%">
                          +25%
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => handleUpdateStatus(action.id, 'completed', 100)} className="text-green-600" title="Complete">
                          <CheckCircle size={16} />
                        </Button>
                      </>
                    )}
                    <Button variant="ghost" size="sm" onClick={() => handleDelete(action.id)} className="text-red-500 hover:text-red-700">
                      <X size={16} />
                    </Button>
                  </div>
                </div>

                {/* Milestones (expanded) */}
                {expandedAction === action.id && (
                  <div className="mt-4 pt-4 border-t">
                    <h4 className="text-sm font-semibold mb-2">{language === 'ar' ? 'المعالم' : 'Milestones'}</h4>
                    {(milestones[action.id] || []).length === 0 ? (
                      <p className="text-xs text-slate-400 mb-3">{language === 'ar' ? 'لا توجد معالم بعد' : 'No milestones yet'}</p>
                    ) : (
                      <div className="space-y-2 mb-3">
                        {(milestones[action.id] || []).map((m: Milestone) => (
                          <div key={m.id} className="flex items-center gap-2 text-sm">
                            <button onClick={() => handleToggleMilestone(m.id, m.is_completed, action.id)} className={`w-5 h-5 rounded border flex items-center justify-center ${m.is_completed ? 'bg-green-500 border-green-500 text-white' : 'border-slate-300'}`}>
                              {m.is_completed && <CheckCircle size={12} />}
                            </button>
                            <span className={m.is_completed ? 'line-through text-slate-400' : 'text-slate-700'}>{m.title}</span>
                            {m.target_date && <span className="text-xs text-slate-400">{new Date(m.target_date).toLocaleDateString()}</span>}
                          </div>
                        ))}
                      </div>
                    )}
                    {/* Add milestone */}
                    <div className="flex gap-2">
                      <Input className="text-sm" placeholder={language === 'ar' ? 'عنوان المعلم...' : 'Milestone title...'} value={milestoneForm.title} onChange={e => setMilestoneForm({ ...milestoneForm, title: e.target.value })} />
                      <Input type="date" className="text-sm w-40" value={milestoneForm.target_date} onChange={e => setMilestoneForm({ ...milestoneForm, target_date: e.target.value })} />
                      <Button size="sm" onClick={() => handleCreateMilestone(action.id)} disabled={!milestoneForm.title}>
                        <Plus size={14} />
                      </Button>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
