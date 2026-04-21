import { useState, useEffect } from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { AlertTriangle, Plus, X, MessageSquare } from 'lucide-react';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface Finding {
  id: string;
  engagement_id: string;
  title: string;
  title_ar?: string;
  description: string;
  severity: string;
  status: string;
  root_cause?: string;
  owner?: string;
  due_date?: string;
  closed_at?: string;
  created_at?: string;
}

interface MgmtResponse {
  id: string;
  finding_id: string;
  response_text: string;
  owner?: string;
  status: string;
  due_date?: string;
}

interface EngOption { id: string; title: string; }

const SEVERITIES = ['low', 'medium', 'high', 'critical'];
const F_STATUSES = ['draft', 'open', 'in_remediation', 'pending_closure', 'closed'];
const R_STATUSES = ['pending', 'accepted', 'in_progress', 'completed', 'overdue'];

export default function AuditFindingPage() {
  const { language } = useLanguage();
  const [findings, setFindings] = useState<Finding[]>([]);
  const [engagements, setEngagements] = useState<EngOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [showResponse, setShowResponse] = useState<string | null>(null);
  const [responses, setResponses] = useState<MgmtResponse[]>([]);
  const [filterSeverity, setFilterSeverity] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [form, setForm] = useState({
    engagement_id: '', title: '', title_ar: '', description: '', description_ar: '',
    severity: 'medium', status: 'open', root_cause: '', owner: '', due_date: '',
  });
  const [respForm, setRespForm] = useState({ response_text: '', owner: '', due_date: '', status: 'pending' });

  const token = localStorage.getItem('token');
  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  const fetchData = () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (filterSeverity) params.set('severity', filterSeverity);
    if (filterStatus) params.set('status', filterStatus);
    Promise.all([
      fetch(`${API}/api/grc/audit-findings?${params}`, { headers }).then(r => r.json()),
      fetch(`${API}/api/grc/audit-engagements`, { headers }).then(r => r.json()),
    ]).then(([fData, eData]) => {
      setFindings(fData.items || []);
      setEngagements((eData.items || []).map((e: { id: string; title: string }) => ({ id: e.id, title: e.title })));
    }).catch(() => {}).finally(() => setLoading(false));
  };

  useEffect(() => { fetchData(); }, [filterSeverity, filterStatus]);

  const handleCreate = async () => {
    if (!form.engagement_id) return;
    const body: Record<string, unknown> = { ...form };
    delete body.engagement_id;
    if (!body.due_date) delete body.due_date;
    const res = await fetch(`${API}/api/grc/audit-findings/${form.engagement_id}`, { method: 'POST', headers, body: JSON.stringify(body) });
    if (res.ok) {
      setShowCreate(false);
      setForm({ engagement_id: '', title: '', title_ar: '', description: '', description_ar: '', severity: 'medium', status: 'open', root_cause: '', owner: '', due_date: '' });
      fetchData();
    }
  };

  const handleDelete = async (id: string) => {
    await fetch(`${API}/api/grc/audit-findings/${id}`, { method: 'DELETE', headers });
    fetchData();
  };

  const loadResponses = async (findingId: string) => {
    if (showResponse === findingId) { setShowResponse(null); return; }
    setShowResponse(findingId);
    const res = await fetch(`${API}/api/grc/management-responses?finding_id=${findingId}`, { headers });
    const data = await res.json();
    setResponses(data.items || []);
  };

  const handleCreateResponse = async () => {
    if (!showResponse) return;
    const body: Record<string, unknown> = { ...respForm };
    if (!body.due_date) delete body.due_date;
    const res = await fetch(`${API}/api/grc/management-responses/${showResponse}`, { method: 'POST', headers, body: JSON.stringify(body) });
    if (res.ok) {
      setRespForm({ response_text: '', owner: '', due_date: '', status: 'pending' });
      loadResponses(showResponse);
    }
  };

  const sevColor = (s: string) => {
    switch (s) {
      case 'critical': return 'bg-red-100 text-red-800';
      case 'high': return 'bg-orange-100 text-orange-800';
      case 'medium': return 'bg-yellow-100 text-yellow-800';
      default: return 'bg-green-100 text-green-800';
    }
  };

  const statusColor = (s: string) => {
    switch (s) {
      case 'open': return 'bg-blue-100 text-blue-800';
      case 'in_remediation': return 'bg-yellow-100 text-yellow-800';
      case 'pending_closure': return 'bg-purple-100 text-purple-800';
      case 'closed': return 'bg-green-100 text-green-800';
      default: return 'bg-slate-100 text-slate-800';
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            {language === 'ar' ? 'نتائج التدقيق' : 'Audit Findings'}
          </h1>
          <p className="text-slate-500 mt-1">
            {language === 'ar' ? 'إدارة نتائج التدقيق والاستجابات الإدارية' : 'Manage audit findings and management responses'}
          </p>
        </div>
        <Button onClick={() => setShowCreate(!showCreate)}>
          {showCreate ? <X size={16} className="me-2" /> : <Plus size={16} className="me-2" />}
          {showCreate ? (language === 'ar' ? 'إلغاء' : 'Cancel') : (language === 'ar' ? 'إضافة نتيجة' : 'Add Finding')}
        </Button>
      </div>

      <div className="flex gap-3 flex-wrap">
        <select value={filterSeverity} onChange={e => setFilterSeverity(e.target.value)} className="border rounded-md px-3 py-2 text-sm">
          <option value="">{language === 'ar' ? 'كل الخطورات' : 'All Severities'}</option>
          {SEVERITIES.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)} className="border rounded-md px-3 py-2 text-sm">
          <option value="">{language === 'ar' ? 'كل الحالات' : 'All Statuses'}</option>
          {F_STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {showCreate && (
        <Card className="border-blue-200 bg-blue-50/30">
          <CardHeader><CardTitle>{language === 'ar' ? 'إضافة نتيجة تدقيق جديدة' : 'Add New Finding'}</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'مهمة التدقيق' : 'Engagement'} *</label>
                <select className="w-full border rounded-md px-3 py-2 text-sm" value={form.engagement_id} onChange={e => setForm({ ...form, engagement_id: e.target.value })}>
                  <option value="">{language === 'ar' ? 'اختر مهمة...' : 'Select engagement...'}</option>
                  {engagements.map(e => <option key={e.id} value={e.id}>{e.title}</option>)}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'الخطورة' : 'Severity'}</label>
                <select className="w-full border rounded-md px-3 py-2 text-sm" value={form.severity} onChange={e => setForm({ ...form, severity: e.target.value })}>
                  {SEVERITIES.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'العنوان (EN)' : 'Title (EN)'}</label>
                <Input value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} placeholder="Finding title..." />
              </div>
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'العنوان (AR)' : 'Title (AR)'}</label>
                <Input value={form.title_ar} onChange={e => setForm({ ...form, title_ar: e.target.value })} placeholder="عنوان النتيجة..." dir="rtl" />
              </div>
              <div className="md:col-span-2">
                <label className="text-sm font-medium">{language === 'ar' ? 'الوصف' : 'Description'} *</label>
                <textarea className="w-full border rounded-md p-2 text-sm" rows={2} value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} />
              </div>
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'السبب الجذري' : 'Root Cause'}</label>
                <Input value={form.root_cause} onChange={e => setForm({ ...form, root_cause: e.target.value })} placeholder="Root cause..." />
              </div>
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'المالك' : 'Owner'}</label>
                <Input value={form.owner} onChange={e => setForm({ ...form, owner: e.target.value })} placeholder="Finding owner..." />
              </div>
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'تاريخ الاستحقاق' : 'Due Date'}</label>
                <Input type="date" value={form.due_date} onChange={e => setForm({ ...form, due_date: e.target.value })} />
              </div>
            </div>
            <Button onClick={handleCreate} disabled={!form.title || !form.description || !form.engagement_id}>
              {language === 'ar' ? 'إنشاء النتيجة' : 'Create Finding'}
            </Button>
          </CardContent>
        </Card>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-32"><div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" /></div>
      ) : findings.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <AlertTriangle size={48} className="mx-auto text-slate-300 mb-4" />
            <p className="text-slate-500">{language === 'ar' ? 'لا توجد نتائج تدقيق بعد' : 'No audit findings yet'}</p>
            <p className="text-sm text-slate-400 mt-1">{language === 'ar' ? 'أنشئ مهمة تدقيق أولاً ثم سجل النتائج' : 'Create an engagement first, then record findings'}</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {findings.map(f => (
            <div key={f.id}>
              <Card className="hover:shadow-md transition-shadow">
                <CardContent className="py-4">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <AlertTriangle size={16} className="text-amber-500" />
                        <h3 className="font-semibold text-slate-800">
                          {language === 'ar' && f.title_ar ? f.title_ar : f.title}
                        </h3>
                        <Badge className={`text-xs ${sevColor(f.severity)}`}>{f.severity}</Badge>
                        <Badge className={`text-xs ${statusColor(f.status)}`}>{f.status}</Badge>
                      </div>
                      <p className="text-sm text-slate-500 line-clamp-1 mb-2">{f.description}</p>
                      <div className="flex items-center gap-4 text-xs text-slate-400">
                        {f.root_cause && <span>{language === 'ar' ? 'السبب' : 'Cause'}: {f.root_cause}</span>}
                        {f.owner && <span>{language === 'ar' ? 'المالك' : 'Owner'}: {f.owner}</span>}
                        {f.due_date && <span>{language === 'ar' ? 'الاستحقاق' : 'Due'}: {f.due_date.split('T')[0]}</span>}
                      </div>
                    </div>
                    <div className="flex gap-1">
                      <Button variant="ghost" size="sm" onClick={() => loadResponses(f.id)} className="text-blue-500 hover:text-blue-700">
                        <MessageSquare size={16} />
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => handleDelete(f.id)} className="text-red-500 hover:text-red-700">
                        <X size={16} />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {showResponse === f.id && (
                <Card className="ms-8 mt-2 border-indigo-200 bg-indigo-50/30">
                  <CardHeader className="pb-2"><CardTitle className="text-sm">{language === 'ar' ? 'الاستجابات الإدارية' : 'Management Responses'}</CardTitle></CardHeader>
                  <CardContent className="space-y-3">
                    {responses.map(r => (
                      <div key={r.id} className="p-3 bg-white rounded-md border text-sm">
                        <div className="flex items-center gap-2 mb-1">
                          <Badge variant="outline" className="text-xs">{r.status}</Badge>
                          {r.owner && <span className="text-xs text-slate-400">{r.owner}</span>}
                          {r.due_date && <span className="text-xs text-slate-400">{language === 'ar' ? 'الاستحقاق' : 'Due'}: {r.due_date.split('T')[0]}</span>}
                        </div>
                        <p className="text-slate-700">{r.response_text}</p>
                      </div>
                    ))}
                    <div className="border-t pt-3 space-y-2">
                      <textarea className="w-full border rounded-md p-2 text-sm" rows={2} placeholder={language === 'ar' ? 'نص الاستجابة...' : 'Response text...'} value={respForm.response_text} onChange={e => setRespForm({ ...respForm, response_text: e.target.value })} />
                      <div className="flex gap-2">
                        <Input className="flex-1" placeholder={language === 'ar' ? 'المالك' : 'Owner'} value={respForm.owner} onChange={e => setRespForm({ ...respForm, owner: e.target.value })} />
                        <Input type="date" className="flex-1" value={respForm.due_date} onChange={e => setRespForm({ ...respForm, due_date: e.target.value })} />
                        <select className="border rounded-md px-2 py-1 text-sm" value={respForm.status} onChange={e => setRespForm({ ...respForm, status: e.target.value })}>
                          {R_STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
                        </select>
                      </div>
                      <Button size="sm" onClick={handleCreateResponse} disabled={!respForm.response_text}>
                        {language === 'ar' ? 'إضافة استجابة' : 'Add Response'}
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
