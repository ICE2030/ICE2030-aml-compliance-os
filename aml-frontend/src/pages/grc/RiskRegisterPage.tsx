import { useState, useEffect } from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import {
  Shield, Plus, TrendingUp, TrendingDown, Minus, Sparkles, X, AlertTriangle,
} from 'lucide-react';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface Risk {
  id: string;
  title: string;
  title_ar?: string;
  description: string;
  category: string;
  subcategory?: string;
  business_unit?: string;
  inherent_likelihood: string;
  inherent_impact: string;
  inherent_score: number;
  residual_likelihood: string;
  residual_impact: string;
  residual_score: number;
  treatment_strategy: string;
  owner?: string;
  status: string;
  trend_direction: string;
  created_at?: string;
}

const CATEGORIES = ['regulatory', 'compliance', 'operational', 'fraud', 'strategic', 'financial', 'technology', 'third_party', 'conduct', 'reputational'];
const LIKELIHOODS = ['rare', 'unlikely', 'possible', 'likely', 'almost_certain'];
const IMPACTS = ['insignificant', 'minor', 'moderate', 'major', 'severe'];
const STATUSES = ['identified', 'assessed', 'treating', 'monitoring', 'closed'];
const TREATMENTS = ['accept', 'mitigate', 'transfer', 'avoid'];

export default function RiskRegisterPage() {
  const { language } = useLanguage();
  const [risks, setRisks] = useState<Risk[]>([]);
  const [summary, setSummary] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [filterCat, setFilterCat] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [form, setForm] = useState({
    title: '', title_ar: '', description: '', description_ar: '',
    category: 'operational', inherent_likelihood: 'possible', inherent_impact: 'moderate',
    residual_likelihood: 'possible', residual_impact: 'moderate',
    treatment_strategy: 'mitigate', owner: '', business_unit: '', root_cause: '',
  });

  const token = localStorage.getItem('token');
  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  const fetchData = () => {
    setLoading(true);
    setError(null);
    const params = new URLSearchParams();
    if (filterCat) params.set('category', filterCat);
    if (filterStatus) params.set('status', filterStatus);

    Promise.all([
      fetch(`${API}/api/grc/risks?${params}`, { headers }).then(r => { if (!r.ok) throw new Error(`API ${r.status}`); return r.json(); }),
      fetch(`${API}/api/grc/risks/summary`, { headers }).then(r => { if (!r.ok) throw new Error(`API ${r.status}`); return r.json(); }),
    ]).then(([risksData, summaryData]) => {
      setRisks(risksData.items || []);
      setSummary(summaryData);
    }).catch((e) => setError(e instanceof Error ? e.message : 'Failed to load risks')).finally(() => setLoading(false));
  };

  useEffect(() => { fetchData(); }, [filterCat, filterStatus]);

  const handleCreate = async () => {
    try {
      const res = await fetch(`${API}/api/grc/risks`, { method: 'POST', headers, body: JSON.stringify(form) });
      if (!res.ok) { setError(`Failed to create risk: ${res.status}`); return; }
      setShowCreate(false);
      setForm({ title: '', title_ar: '', description: '', description_ar: '', category: 'operational', inherent_likelihood: 'possible', inherent_impact: 'moderate', residual_likelihood: 'possible', residual_impact: 'moderate', treatment_strategy: 'mitigate', owner: '', business_unit: '', root_cause: '' });
      fetchData();
    } catch (e) { setError(e instanceof Error ? e.message : 'Failed to create risk'); }
  };

  const handleDelete = async (id: string) => {
    try {
      const res = await fetch(`${API}/api/grc/risks/${id}`, { method: 'DELETE', headers });
      if (!res.ok) { setError(`Failed to delete risk: ${res.status}`); return; }
      fetchData();
    } catch (e) { setError(e instanceof Error ? e.message : 'Failed to delete risk'); }
  };

  const scoreColor = (score: number) => {
    if (score >= 0.64) return 'bg-red-100 text-red-800';
    if (score >= 0.48) return 'bg-orange-100 text-orange-800';
    if (score >= 0.24) return 'bg-yellow-100 text-yellow-800';
    return 'bg-green-100 text-green-800';
  };

  const trendIcon = (trend: string) => {
    switch (trend) {
      case 'improving': return <TrendingDown size={14} className="text-green-600" />;
      case 'deteriorating': return <TrendingUp size={14} className="text-red-600" />;
      case 'stable': return <Minus size={14} className="text-slate-500" />;
      default: return <Sparkles size={14} className="text-blue-500" />;
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            {language === 'ar' ? 'سجل المخاطر المؤسسية' : 'Enterprise Risk Register'}
          </h1>
          <p className="text-slate-500 mt-1">
            {language === 'ar' ? 'إدارة المخاطر المؤسسية مع التسجيل والتقييم والمعالجة' : 'Enterprise risk management with scoring, treatment, and trends'}
          </p>
        </div>
        <Button onClick={() => setShowCreate(!showCreate)}>
          {showCreate ? <X size={16} className="me-2" /> : <Plus size={16} className="me-2" />}
          {showCreate ? (language === 'ar' ? 'إلغاء' : 'Cancel') : (language === 'ar' ? 'إضافة مخاطرة' : 'Add Risk')}
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

      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card><CardContent className="pt-4 text-center">
            <p className="text-sm text-slate-500">{language === 'ar' ? 'الإجمالي' : 'Total'}</p>
            <p className="text-2xl font-bold">{(summary as { total?: number }).total || 0}</p>
          </CardContent></Card>
          <Card><CardContent className="pt-4 text-center">
            <p className="text-sm text-slate-500">{language === 'ar' ? 'عالية' : 'High Risk'}</p>
            <p className="text-2xl font-bold text-red-600">{(summary as { high_risks?: number }).high_risks || 0}</p>
          </CardContent></Card>
          <Card><CardContent className="pt-4 text-center">
            <p className="text-sm text-slate-500">{language === 'ar' ? 'متوسط النتيجة الكامنة' : 'Avg Inherent'}</p>
            <p className="text-2xl font-bold">{((summary as { avg_inherent_score?: number }).avg_inherent_score || 0).toFixed(2)}</p>
          </CardContent></Card>
          <Card><CardContent className="pt-4 text-center">
            <p className="text-sm text-slate-500">{language === 'ar' ? 'متوسط النتيجة المتبقية' : 'Avg Residual'}</p>
            <p className="text-2xl font-bold">{((summary as { avg_residual_score?: number }).avg_residual_score || 0).toFixed(2)}</p>
          </CardContent></Card>
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-3 flex-wrap">
        <select value={filterCat} onChange={e => setFilterCat(e.target.value)} className="border rounded-md px-3 py-2 text-sm">
          <option value="">{language === 'ar' ? 'كل الفئات' : 'All Categories'}</option>
          {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)} className="border rounded-md px-3 py-2 text-sm">
          <option value="">{language === 'ar' ? 'كل الحالات' : 'All Statuses'}</option>
          {STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {/* Create Form */}
      {showCreate && (
        <Card className="border-blue-200 bg-blue-50/30">
          <CardHeader><CardTitle>{language === 'ar' ? 'إضافة مخاطرة جديدة' : 'Add New Risk'}</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'العنوان (EN)' : 'Title (EN)'}</label>
                <Input value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} placeholder="Risk title..." />
              </div>
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'العنوان (AR)' : 'Title (AR)'}</label>
                <Input value={form.title_ar} onChange={e => setForm({ ...form, title_ar: e.target.value })} placeholder="عنوان المخاطرة..." dir="rtl" />
              </div>
              <div className="md:col-span-2">
                <label className="text-sm font-medium">{language === 'ar' ? 'الوصف' : 'Description'}</label>
                <textarea className="w-full border rounded-md p-2 text-sm" rows={2} value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} />
              </div>
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'الفئة' : 'Category'}</label>
                <select className="w-full border rounded-md px-3 py-2 text-sm" value={form.category} onChange={e => setForm({ ...form, category: e.target.value })}>
                  {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'استراتيجية المعالجة' : 'Treatment Strategy'}</label>
                <select className="w-full border rounded-md px-3 py-2 text-sm" value={form.treatment_strategy} onChange={e => setForm({ ...form, treatment_strategy: e.target.value })}>
                  {TREATMENTS.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'الاحتمال الكامن' : 'Inherent Likelihood'}</label>
                <select className="w-full border rounded-md px-3 py-2 text-sm" value={form.inherent_likelihood} onChange={e => setForm({ ...form, inherent_likelihood: e.target.value })}>
                  {LIKELIHOODS.map(l => <option key={l} value={l}>{l}</option>)}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'الأثر الكامن' : 'Inherent Impact'}</label>
                <select className="w-full border rounded-md px-3 py-2 text-sm" value={form.inherent_impact} onChange={e => setForm({ ...form, inherent_impact: e.target.value })}>
                  {IMPACTS.map(i => <option key={i} value={i}>{i}</option>)}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'الاحتمال المتبقي' : 'Residual Likelihood'}</label>
                <select className="w-full border rounded-md px-3 py-2 text-sm" value={form.residual_likelihood} onChange={e => setForm({ ...form, residual_likelihood: e.target.value })}>
                  {LIKELIHOODS.map(l => <option key={l} value={l}>{l}</option>)}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'الأثر المتبقي' : 'Residual Impact'}</label>
                <select className="w-full border rounded-md px-3 py-2 text-sm" value={form.residual_impact} onChange={e => setForm({ ...form, residual_impact: e.target.value })}>
                  {IMPACTS.map(i => <option key={i} value={i}>{i}</option>)}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'المالك' : 'Owner'}</label>
                <Input value={form.owner} onChange={e => setForm({ ...form, owner: e.target.value })} placeholder="Risk owner..." />
              </div>
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'وحدة الأعمال' : 'Business Unit'}</label>
                <Input value={form.business_unit} onChange={e => setForm({ ...form, business_unit: e.target.value })} placeholder="Business unit..." />
              </div>
            </div>
            <Button onClick={handleCreate} disabled={!form.title || !form.description}>
              {language === 'ar' ? 'إنشاء المخاطرة' : 'Create Risk'}
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Risk List */}
      {loading ? (
        <div className="flex items-center justify-center h-32"><div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" /></div>
      ) : risks.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <Shield size={48} className="mx-auto text-slate-300 mb-4" />
            <p className="text-slate-500">{language === 'ar' ? 'لم يتم تسجيل مخاطر بعد' : 'No risks registered yet'}</p>
            <p className="text-sm text-slate-400 mt-1">{language === 'ar' ? 'انقر "إضافة مخاطرة" لبدء بناء سجل المخاطر' : 'Click "Add Risk" to start building the risk register'}</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {risks.map(risk => (
            <Card key={risk.id} className="hover:shadow-md transition-shadow">
              <CardContent className="py-4">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      {trendIcon(risk.trend_direction)}
                      <h3 className="font-semibold text-slate-800">
                        {language === 'ar' && risk.title_ar ? risk.title_ar : risk.title}
                      </h3>
                      <Badge variant="outline" className="text-xs">{risk.category}</Badge>
                      <Badge variant="outline" className="text-xs">{risk.status}</Badge>
                    </div>
                    <p className="text-sm text-slate-500 line-clamp-1 mb-2">{risk.description}</p>
                    <div className="flex items-center gap-4 text-xs">
                      <span className="text-slate-400">
                        {language === 'ar' ? 'كامن' : 'Inherent'}: <span className={`px-1.5 py-0.5 rounded ${scoreColor(risk.inherent_score)}`}>{(risk.inherent_score * 100).toFixed(0)}%</span>
                      </span>
                      <span className="text-slate-400">→</span>
                      <span className="text-slate-400">
                        {language === 'ar' ? 'متبقي' : 'Residual'}: <span className={`px-1.5 py-0.5 rounded ${scoreColor(risk.residual_score)}`}>{(risk.residual_score * 100).toFixed(0)}%</span>
                      </span>
                      <span className="text-slate-400">{language === 'ar' ? 'معالجة' : 'Treatment'}: {risk.treatment_strategy}</span>
                      {risk.owner && <span className="text-slate-400">{language === 'ar' ? 'المالك' : 'Owner'}: {risk.owner}</span>}
                    </div>
                  </div>
                  <Button variant="ghost" size="sm" onClick={() => handleDelete(risk.id)} className="text-red-500 hover:text-red-700">
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
