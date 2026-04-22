import { useState, useEffect } from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { ClipboardList, Plus, X } from 'lucide-react';
import { EmptyState } from '@/components/EmptyState';
import { trackUsage } from '@/hooks/useUsageTracking';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface AuditPlan {
  id: string;
  title: string;
  title_ar?: string;
  description?: string;
  period_start?: string;
  period_end?: string;
  scope_summary?: string;
  owner?: string;
  status: string;
  created_at?: string;
}

const STATUSES = ['draft', 'approved', 'in_progress', 'completed', 'cancelled'];

export default function AuditPlanPage() {
  const { language, t } = useLanguage();
  const [plans, setPlans] = useState<AuditPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [filterStatus, setFilterStatus] = useState('');
  const [form, setForm] = useState({
    title: '', title_ar: '', description: '', scope_summary: '', owner: '', status: 'draft',
    period_start: '', period_end: '',
  });

  const token = localStorage.getItem('token');
  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  const fetchData = () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (filterStatus) params.set('status', filterStatus);
    fetch(`${API}/api/grc/audit-plans?${params}`, { headers })
      .then(r => r.json())
      .then(data => setPlans(data.items || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchData(); }, [filterStatus]);

  const handleCreate = async () => {
    const body: Record<string, unknown> = { ...form };
    if (!body.period_start) delete body.period_start;
    if (!body.period_end) delete body.period_end;
    const res = await fetch(`${API}/api/grc/audit-plans`, { method: 'POST', headers, body: JSON.stringify(body) });
    if (res.ok) {
      const created = await res.json().catch(() => ({} as { id?: string }));
      trackUsage('create', { resource_type: 'audit_plan', resource_id: created?.id, path: '/grc/audit/plans' });
      setShowCreate(false);
      setForm({ title: '', title_ar: '', description: '', scope_summary: '', owner: '', status: 'draft', period_start: '', period_end: '' });
      fetchData();
    }
  };

  const handleDelete = async (id: string) => {
    await fetch(`${API}/api/grc/audit-plans/${id}`, { method: 'DELETE', headers });
    trackUsage('delete', { resource_type: 'audit_plan', resource_id: id, path: '/grc/audit/plans' });
    fetchData();
  };

  const statusColor = (s: string) => {
    switch (s) {
      case 'approved': return 'bg-blue-100 text-blue-800';
      case 'in_progress': return 'bg-yellow-100 text-yellow-800';
      case 'completed': return 'bg-green-100 text-green-800';
      case 'cancelled': return 'bg-red-100 text-red-800';
      default: return 'bg-slate-100 text-slate-800';
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            {language === 'ar' ? 'خطط التدقيق' : 'Audit Plans'}
          </h1>
          <p className="text-slate-500 mt-1">
            {language === 'ar' ? 'إدارة خطط التدقيق الداخلي والنطاق والجدول الزمني' : 'Manage internal audit plans, scope, and scheduling'}
          </p>
        </div>
        <Button onClick={() => setShowCreate(!showCreate)}>
          {showCreate ? <X size={16} className="me-2" /> : <Plus size={16} className="me-2" />}
          {showCreate ? (language === 'ar' ? 'إلغاء' : 'Cancel') : (language === 'ar' ? 'إضافة خطة' : 'Add Plan')}
        </Button>
      </div>

      <div className="flex gap-3 flex-wrap">
        <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)} className="border rounded-md px-3 py-2 text-sm">
          <option value="">{language === 'ar' ? 'كل الحالات' : 'All Statuses'}</option>
          {STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {showCreate && (
        <Card className="border-blue-200 bg-blue-50/30">
          <CardHeader><CardTitle>{language === 'ar' ? 'إنشاء خطة تدقيق جديدة' : 'Create New Audit Plan'}</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'العنوان (EN)' : 'Title (EN)'}</label>
                <Input value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} placeholder="Audit plan title..." />
              </div>
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'العنوان (AR)' : 'Title (AR)'}</label>
                <Input value={form.title_ar} onChange={e => setForm({ ...form, title_ar: e.target.value })} placeholder="عنوان خطة التدقيق..." dir="rtl" />
              </div>
              <div className="md:col-span-2">
                <label className="text-sm font-medium">{language === 'ar' ? 'الوصف' : 'Description'}</label>
                <textarea className="w-full border rounded-md p-2 text-sm" rows={2} value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} />
              </div>
              <div className="md:col-span-2">
                <label className="text-sm font-medium">{language === 'ar' ? 'ملخص النطاق' : 'Scope Summary'}</label>
                <textarea className="w-full border rounded-md p-2 text-sm" rows={2} value={form.scope_summary} onChange={e => setForm({ ...form, scope_summary: e.target.value })} />
              </div>
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'بداية الفترة' : 'Period Start'}</label>
                <Input type="date" value={form.period_start} onChange={e => setForm({ ...form, period_start: e.target.value })} />
              </div>
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'نهاية الفترة' : 'Period End'}</label>
                <Input type="date" value={form.period_end} onChange={e => setForm({ ...form, period_end: e.target.value })} />
              </div>
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'المالك' : 'Owner'}</label>
                <Input value={form.owner} onChange={e => setForm({ ...form, owner: e.target.value })} placeholder="Plan owner..." />
              </div>
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'الحالة' : 'Status'}</label>
                <select className="w-full border rounded-md px-3 py-2 text-sm" value={form.status} onChange={e => setForm({ ...form, status: e.target.value })}>
                  {STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
            </div>
            <Button onClick={handleCreate} disabled={!form.title}>
              {language === 'ar' ? 'إنشاء الخطة' : 'Create Plan'}
            </Button>
          </CardContent>
        </Card>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-32"><div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" /></div>
      ) : plans.length === 0 ? (
        <EmptyState
          icon={<ClipboardList size={48} />}
          title={t('empty.audit_plans_title')}
          hint={t('empty.audit_plans_hint')}
          primaryAction={
            <Button onClick={() => setShowCreate(true)}>
              <Plus size={16} className="me-2" />
              {language === 'ar' ? 'إضافة خطة' : 'Add Plan'}
            </Button>
          }
          showLoadSamples
          onSamplesLoaded={fetchData}
        />
      ) : (
        <div className="space-y-3">
          {plans.map(plan => (
            <Card key={plan.id} className="hover:shadow-md transition-shadow">
              <CardContent className="py-4">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <ClipboardList size={16} className="text-blue-500" />
                      <h3 className="font-semibold text-slate-800">
                        {language === 'ar' && plan.title_ar ? plan.title_ar : plan.title}
                      </h3>
                      <Badge className={`text-xs ${statusColor(plan.status)}`}>{plan.status}</Badge>
                    </div>
                    {plan.description && <p className="text-sm text-slate-500 line-clamp-1 mb-2">{plan.description}</p>}
                    <div className="flex items-center gap-4 text-xs text-slate-400">
                      {plan.period_start && <span>{language === 'ar' ? 'من' : 'From'}: {plan.period_start.split('T')[0]}</span>}
                      {plan.period_end && <span>{language === 'ar' ? 'إلى' : 'To'}: {plan.period_end.split('T')[0]}</span>}
                      {plan.owner && <span>{language === 'ar' ? 'المالك' : 'Owner'}: {plan.owner}</span>}
                    </div>
                  </div>
                  <Button variant="ghost" size="sm" onClick={() => handleDelete(plan.id)} className="text-red-500 hover:text-red-700">
                    <X size={16} />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
