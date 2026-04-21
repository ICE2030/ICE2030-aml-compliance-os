import { useState, useEffect } from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Search, Plus, X } from 'lucide-react';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface Engagement {
  id: string;
  plan_id: string;
  title: string;
  title_ar?: string;
  description?: string;
  scope?: string;
  objectives?: string;
  start_date?: string;
  end_date?: string;
  owner?: string;
  status: string;
  created_at?: string;
}

interface PlanOption { id: string; title: string; }

const STATUSES = ['planned', 'fieldwork', 'reporting', 'completed', 'cancelled'];

export default function AuditEngagementPage() {
  const { language } = useLanguage();
  const [engagements, setEngagements] = useState<Engagement[]>([]);
  const [plans, setPlans] = useState<PlanOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [filterStatus, setFilterStatus] = useState('');
  const [filterPlan, setFilterPlan] = useState('');
  const [form, setForm] = useState({
    title: '', title_ar: '', description: '', scope: '', objectives: '',
    plan_id: '', owner: '', status: 'planned', start_date: '', end_date: '',
  });

  const token = localStorage.getItem('token');
  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  const fetchData = () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (filterStatus) params.set('status', filterStatus);
    if (filterPlan) params.set('plan_id', filterPlan);
    Promise.all([
      fetch(`${API}/api/grc/audit-engagements?${params}`, { headers }).then(r => r.json()),
      fetch(`${API}/api/grc/audit-plans`, { headers }).then(r => r.json()),
    ]).then(([engData, planData]) => {
      setEngagements(engData.items || []);
      setPlans((planData.items || []).map((p: { id: string; title: string }) => ({ id: p.id, title: p.title })));
    }).catch(() => {}).finally(() => setLoading(false));
  };

  useEffect(() => { fetchData(); }, [filterStatus, filterPlan]);

  const handleCreate = async () => {
    const body: Record<string, unknown> = { ...form };
    if (!body.start_date) delete body.start_date;
    if (!body.end_date) delete body.end_date;
    if (!body.plan_id) { delete body.plan_id; return; }
    const res = await fetch(`${API}/api/grc/audit-engagements`, { method: 'POST', headers, body: JSON.stringify(body) });
    if (res.ok) {
      setShowCreate(false);
      setForm({ title: '', title_ar: '', description: '', scope: '', objectives: '', plan_id: '', owner: '', status: 'planned', start_date: '', end_date: '' });
      fetchData();
    }
  };

  const handleDelete = async (id: string) => {
    await fetch(`${API}/api/grc/audit-engagements/${id}`, { method: 'DELETE', headers });
    fetchData();
  };

  const statusColor = (s: string) => {
    switch (s) {
      case 'fieldwork': return 'bg-yellow-100 text-yellow-800';
      case 'reporting': return 'bg-blue-100 text-blue-800';
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
            {language === 'ar' ? 'مهام التدقيق' : 'Audit Engagements'}
          </h1>
          <p className="text-slate-500 mt-1">
            {language === 'ar' ? 'إدارة مهام التدقيق والنطاق والأهداف' : 'Manage audit engagements, scope, objectives, and risk-based planning'}
          </p>
        </div>
        <Button onClick={() => setShowCreate(!showCreate)}>
          {showCreate ? <X size={16} className="me-2" /> : <Plus size={16} className="me-2" />}
          {showCreate ? (language === 'ar' ? 'إلغاء' : 'Cancel') : (language === 'ar' ? 'إضافة مهمة' : 'Add Engagement')}
        </Button>
      </div>

      <div className="flex gap-3 flex-wrap">
        <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)} className="border rounded-md px-3 py-2 text-sm">
          <option value="">{language === 'ar' ? 'كل الحالات' : 'All Statuses'}</option>
          {STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        {plans.length > 0 && (
          <select value={filterPlan} onChange={e => setFilterPlan(e.target.value)} className="border rounded-md px-3 py-2 text-sm">
            <option value="">{language === 'ar' ? 'كل الخطط' : 'All Plans'}</option>
            {plans.map(p => <option key={p.id} value={p.id}>{p.title}</option>)}
          </select>
        )}
      </div>

      {showCreate && (
        <Card className="border-blue-200 bg-blue-50/30">
          <CardHeader><CardTitle>{language === 'ar' ? 'إنشاء مهمة تدقيق جديدة' : 'Create New Engagement'}</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'خطة التدقيق' : 'Audit Plan'} *</label>
                <select className="w-full border rounded-md px-3 py-2 text-sm" value={form.plan_id} onChange={e => setForm({ ...form, plan_id: e.target.value })}>
                  <option value="">{language === 'ar' ? 'اختر خطة...' : 'Select plan...'}</option>
                  {plans.map(p => <option key={p.id} value={p.id}>{p.title}</option>)}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'العنوان (EN)' : 'Title (EN)'}</label>
                <Input value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} placeholder="Engagement title..." />
              </div>
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'العنوان (AR)' : 'Title (AR)'}</label>
                <Input value={form.title_ar} onChange={e => setForm({ ...form, title_ar: e.target.value })} placeholder="عنوان المهمة..." dir="rtl" />
              </div>
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'النطاق' : 'Scope'}</label>
                <Input value={form.scope} onChange={e => setForm({ ...form, scope: e.target.value })} placeholder="Engagement scope..." />
              </div>
              <div className="md:col-span-2">
                <label className="text-sm font-medium">{language === 'ar' ? 'الأهداف' : 'Objectives'}</label>
                <textarea className="w-full border rounded-md p-2 text-sm" rows={2} value={form.objectives} onChange={e => setForm({ ...form, objectives: e.target.value })} />
              </div>
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'تاريخ البدء' : 'Start Date'}</label>
                <Input type="date" value={form.start_date} onChange={e => setForm({ ...form, start_date: e.target.value })} />
              </div>
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'تاريخ الانتهاء' : 'End Date'}</label>
                <Input type="date" value={form.end_date} onChange={e => setForm({ ...form, end_date: e.target.value })} />
              </div>
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'المالك' : 'Owner'}</label>
                <Input value={form.owner} onChange={e => setForm({ ...form, owner: e.target.value })} placeholder="Engagement owner..." />
              </div>
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'الحالة' : 'Status'}</label>
                <select className="w-full border rounded-md px-3 py-2 text-sm" value={form.status} onChange={e => setForm({ ...form, status: e.target.value })}>
                  {STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
            </div>
            <Button onClick={handleCreate} disabled={!form.title || !form.plan_id}>
              {language === 'ar' ? 'إنشاء المهمة' : 'Create Engagement'}
            </Button>
          </CardContent>
        </Card>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-32"><div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" /></div>
      ) : engagements.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <Search size={48} className="mx-auto text-slate-300 mb-4" />
            <p className="text-slate-500">{language === 'ar' ? 'لا توجد مهام تدقيق بعد' : 'No audit engagements yet'}</p>
            <p className="text-sm text-slate-400 mt-1">{language === 'ar' ? 'أنشئ خطة تدقيق أولاً ثم أضف مهام التدقيق' : 'Create an audit plan first, then add engagements'}</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {engagements.map(eng => (
            <Card key={eng.id} className="hover:shadow-md transition-shadow">
              <CardContent className="py-4">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <Search size={16} className="text-indigo-500" />
                      <h3 className="font-semibold text-slate-800">
                        {language === 'ar' && eng.title_ar ? eng.title_ar : eng.title}
                      </h3>
                      <Badge className={`text-xs ${statusColor(eng.status)}`}>{eng.status}</Badge>
                    </div>
                    {eng.scope && <p className="text-sm text-slate-500 line-clamp-1 mb-2">{language === 'ar' ? 'النطاق' : 'Scope'}: {eng.scope}</p>}
                    <div className="flex items-center gap-4 text-xs text-slate-400">
                      {eng.start_date && <span>{language === 'ar' ? 'بدء' : 'Start'}: {eng.start_date.split('T')[0]}</span>}
                      {eng.end_date && <span>{language === 'ar' ? 'انتهاء' : 'End'}: {eng.end_date.split('T')[0]}</span>}
                      {eng.owner && <span>{language === 'ar' ? 'المالك' : 'Owner'}: {eng.owner}</span>}
                    </div>
                  </div>
                  <Button variant="ghost" size="sm" onClick={() => handleDelete(eng.id)} className="text-red-500 hover:text-red-700">
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
