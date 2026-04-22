import { useState, useEffect } from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { CheckCircle, Plus, X, XCircle, AlertCircle, MinusCircle } from 'lucide-react';
import { EmptyState } from '@/components/EmptyState';
import { trackUsage } from '@/hooks/useUsageTracking';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface ControlTestItem {
  id: string;
  engagement_id: string;
  control_id?: string;
  test_type: string;
  procedure: string;
  tester?: string;
  test_date?: string;
  design_result: string;
  operating_result: string;
  overall_result: string;
  sample_size?: number;
  exceptions_found?: number;
  notes?: string;
  created_at?: string;
}

interface EngOption { id: string; title: string; }

const TEST_TYPES = ['design', 'operating', 'both'];
const RESULTS = ['effective', 'partially_effective', 'ineffective', 'not_tested'];

export default function ControlTestPage() {
  const { language, t } = useLanguage();
  const [tests, setTests] = useState<ControlTestItem[]>([]);
  const [engagements, setEngagements] = useState<EngOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [filterEng, setFilterEng] = useState('');
  const [filterResult, setFilterResult] = useState('');
  const [form, setForm] = useState({
    engagement_id: '', procedure: '', procedure_ar: '', test_type: 'both',
    tester: '', test_date: '', design_result: 'not_tested', operating_result: 'not_tested',
    overall_result: 'not_tested', sample_size: '', exceptions_found: '', notes: '',
  });

  const token = localStorage.getItem('token');
  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  const fetchData = () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (filterEng) params.set('engagement_id', filterEng);
    if (filterResult) params.set('result', filterResult);
    Promise.all([
      fetch(`${API}/api/grc/control-tests?${params}`, { headers }).then(r => r.json()),
      fetch(`${API}/api/grc/audit-engagements`, { headers }).then(r => r.json()),
    ]).then(([testData, engData]) => {
      setTests(testData.items || []);
      setEngagements((engData.items || []).map((e: { id: string; title: string }) => ({ id: e.id, title: e.title })));
    }).catch(() => {}).finally(() => setLoading(false));
  };

  useEffect(() => { fetchData(); }, [filterEng, filterResult]);

  const handleCreate = async () => {
    if (!form.engagement_id) return;
    const body: Record<string, unknown> = {
      procedure: form.procedure, procedure_ar: form.procedure_ar,
      test_type: form.test_type, tester: form.tester,
      design_result: form.design_result, operating_result: form.operating_result,
      overall_result: form.overall_result, notes: form.notes,
    };
    if (form.test_date) body.test_date = form.test_date;
    if (form.sample_size) body.sample_size = parseInt(form.sample_size);
    if (form.exceptions_found) body.exceptions_found = parseInt(form.exceptions_found);
    const res = await fetch(`${API}/api/grc/control-tests/${form.engagement_id}`, { method: 'POST', headers, body: JSON.stringify(body) });
    if (res.ok) {
      const created = await res.json().catch(() => ({} as { id?: string }));
      trackUsage('create', { resource_type: 'control_test', resource_id: created?.id, path: '/grc/audit/control-tests' });
      setShowCreate(false);
      setForm({ engagement_id: '', procedure: '', procedure_ar: '', test_type: 'both', tester: '', test_date: '', design_result: 'not_tested', operating_result: 'not_tested', overall_result: 'not_tested', sample_size: '', exceptions_found: '', notes: '' });
      fetchData();
    }
  };

  const handleDelete = async (id: string) => {
    await fetch(`${API}/api/grc/control-tests/${id}`, { method: 'DELETE', headers });
    trackUsage('delete', { resource_type: 'control_test', resource_id: id, path: '/grc/audit/control-tests' });
    fetchData();
  };

  const resultIcon = (r: string) => {
    switch (r) {
      case 'effective': return <CheckCircle size={14} className="text-green-600" />;
      case 'partially_effective': return <AlertCircle size={14} className="text-yellow-600" />;
      case 'ineffective': return <XCircle size={14} className="text-red-600" />;
      default: return <MinusCircle size={14} className="text-slate-400" />;
    }
  };

  const resultColor = (r: string) => {
    switch (r) {
      case 'effective': return 'bg-green-100 text-green-800';
      case 'partially_effective': return 'bg-yellow-100 text-yellow-800';
      case 'ineffective': return 'bg-red-100 text-red-800';
      default: return 'bg-slate-100 text-slate-800';
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            {language === 'ar' ? 'اختبارات الضوابط' : 'Control Tests'}
          </h1>
          <p className="text-slate-500 mt-1">
            {language === 'ar' ? 'اختبار فعالية التصميم والتشغيل للضوابط' : 'Test design and operating effectiveness of controls'}
          </p>
        </div>
        <Button onClick={() => setShowCreate(!showCreate)}>
          {showCreate ? <X size={16} className="me-2" /> : <Plus size={16} className="me-2" />}
          {showCreate ? (language === 'ar' ? 'إلغاء' : 'Cancel') : (language === 'ar' ? 'إضافة اختبار' : 'Add Test')}
        </Button>
      </div>

      <div className="flex gap-3 flex-wrap">
        {engagements.length > 0 && (
          <select value={filterEng} onChange={e => setFilterEng(e.target.value)} className="border rounded-md px-3 py-2 text-sm">
            <option value="">{language === 'ar' ? 'كل المهام' : 'All Engagements'}</option>
            {engagements.map(e => <option key={e.id} value={e.id}>{e.title}</option>)}
          </select>
        )}
        <select value={filterResult} onChange={e => setFilterResult(e.target.value)} className="border rounded-md px-3 py-2 text-sm">
          <option value="">{language === 'ar' ? 'كل النتائج' : 'All Results'}</option>
          {RESULTS.map(r => <option key={r} value={r}>{r}</option>)}
        </select>
      </div>

      {showCreate && (
        <Card className="border-blue-200 bg-blue-50/30">
          <CardHeader><CardTitle>{language === 'ar' ? 'إنشاء اختبار ضابط جديد' : 'Create New Control Test'}</CardTitle></CardHeader>
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
                <label className="text-sm font-medium">{language === 'ar' ? 'نوع الاختبار' : 'Test Type'}</label>
                <select className="w-full border rounded-md px-3 py-2 text-sm" value={form.test_type} onChange={e => setForm({ ...form, test_type: e.target.value })}>
                  {TEST_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div className="md:col-span-2">
                <label className="text-sm font-medium">{language === 'ar' ? 'إجراء الاختبار' : 'Test Procedure'} *</label>
                <textarea className="w-full border rounded-md p-2 text-sm" rows={2} value={form.procedure} onChange={e => setForm({ ...form, procedure: e.target.value })} placeholder="Describe the test procedure..." />
              </div>
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'المختبر' : 'Tester'}</label>
                <Input value={form.tester} onChange={e => setForm({ ...form, tester: e.target.value })} placeholder="Tester name..." />
              </div>
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'تاريخ الاختبار' : 'Test Date'}</label>
                <Input type="date" value={form.test_date} onChange={e => setForm({ ...form, test_date: e.target.value })} />
              </div>
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'نتيجة التصميم' : 'Design Result'}</label>
                <select className="w-full border rounded-md px-3 py-2 text-sm" value={form.design_result} onChange={e => setForm({ ...form, design_result: e.target.value })}>
                  {RESULTS.map(r => <option key={r} value={r}>{r}</option>)}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'نتيجة التشغيل' : 'Operating Result'}</label>
                <select className="w-full border rounded-md px-3 py-2 text-sm" value={form.operating_result} onChange={e => setForm({ ...form, operating_result: e.target.value })}>
                  {RESULTS.map(r => <option key={r} value={r}>{r}</option>)}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'النتيجة الإجمالية' : 'Overall Result'}</label>
                <select className="w-full border rounded-md px-3 py-2 text-sm" value={form.overall_result} onChange={e => setForm({ ...form, overall_result: e.target.value })}>
                  {RESULTS.map(r => <option key={r} value={r}>{r}</option>)}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'حجم العينة' : 'Sample Size'}</label>
                <Input type="number" value={form.sample_size} onChange={e => setForm({ ...form, sample_size: e.target.value })} placeholder="e.g. 25" />
              </div>
              <div>
                <label className="text-sm font-medium">{language === 'ar' ? 'الاستثناءات' : 'Exceptions Found'}</label>
                <Input type="number" value={form.exceptions_found} onChange={e => setForm({ ...form, exceptions_found: e.target.value })} placeholder="e.g. 2" />
              </div>
            </div>
            <Button onClick={handleCreate} disabled={!form.procedure || !form.engagement_id}>
              {language === 'ar' ? 'إنشاء الاختبار' : 'Create Test'}
            </Button>
          </CardContent>
        </Card>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-32"><div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" /></div>
      ) : tests.length === 0 ? (
        <EmptyState
          icon={<CheckCircle size={48} />}
          title={t('empty.control_tests_title')}
          hint={t('empty.control_tests_hint')}
          primaryAction={
            <Button onClick={() => setShowCreate(true)}>
              <Plus size={16} className="me-2" />
              {language === 'ar' ? 'إضافة اختبار' : 'Add Test'}
            </Button>
          }
          showLoadSamples
          onSamplesLoaded={fetchData}
        />
      ) : (
        <div className="space-y-3">
          {tests.map(test => (
            <Card key={test.id} className="hover:shadow-md transition-shadow">
              <CardContent className="py-4">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      {resultIcon(test.overall_result)}
                      <h3 className="font-semibold text-slate-800 line-clamp-1">{test.procedure.substring(0, 100)}{test.procedure.length > 100 ? '...' : ''}</h3>
                      <Badge className={`text-xs ${resultColor(test.overall_result)}`}>{test.overall_result}</Badge>
                      <Badge variant="outline" className="text-xs">{test.test_type}</Badge>
                    </div>
                    <div className="flex items-center gap-4 text-xs text-slate-400 mt-2">
                      <span>{language === 'ar' ? 'تصميم' : 'Design'}: {test.design_result}</span>
                      <span>{language === 'ar' ? 'تشغيل' : 'Operating'}: {test.operating_result}</span>
                      {test.sample_size != null && <span>{language === 'ar' ? 'عينة' : 'Sample'}: {test.sample_size}</span>}
                      {test.exceptions_found != null && <span>{language === 'ar' ? 'استثناءات' : 'Exceptions'}: {test.exceptions_found}</span>}
                      {test.tester && <span>{language === 'ar' ? 'المختبر' : 'Tester'}: {test.tester}</span>}
                      {test.test_date && <span>{test.test_date.split('T')[0]}</span>}
                    </div>
                  </div>
                  <Button variant="ghost" size="sm" onClick={() => handleDelete(test.id)} className="text-red-500 hover:text-red-700">
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
