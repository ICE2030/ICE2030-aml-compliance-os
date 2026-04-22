import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useLanguage } from '@/contexts/LanguageContext';
import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ArrowRight, Compass, PlayCircle, AlertTriangle } from 'lucide-react';
import api from '@/services/api';
import { trackUsage } from '@/hooks/useUsageTracking';

interface DemoStep {
  title_en: string;
  title_ar: string;
  path: string;
  hint_en: string;
  hint_ar: string;
}

interface DemoFlow {
  key: string;
  title_en: string;
  title_ar: string;
  description_en: string;
  description_ar: string;
  steps: DemoStep[];
}

export default function DemoFlowsPage() {
  const { language } = useLanguage();
  const { user } = useAuth();
  const [flows, setFlows] = useState<DemoFlow[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingSamples, setLoadingSamples] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const isAr = language === 'ar';
  const canSeed = user?.role === 'admin' || user?.role === 'compliance_officer';

  useEffect(() => {
    api
      .get('/api/demo/flows')
      .then((r) => setFlows(r.data.flows || []))
      .catch(() => setError(isAr ? 'تعذر تحميل تدفقات العرض' : 'Failed to load demo flows'))
      .finally(() => setLoading(false));
  }, [isAr]);

  const handleFlowOpen = (flow: DemoFlow) => {
    trackUsage('demo_flow_view', {
      resource_type: 'demo_flow',
      resource_id: flow.key,
      metadata: { title: flow.title_en },
    });
  };

  const handleLoadSamples = async () => {
    setLoadingSamples(true);
    setResult(null);
    setError(null);
    try {
      const resp = await api.post('/api/demo/load-samples');
      const s = resp.data.stats || {};
      const total = Object.values(s).reduce<number>((sum, n) => sum + (typeof n === 'number' ? n : 0), 0);
      setResult(
        isAr
          ? `تم إضافة ${total} عنصراً من البيانات الواقعية (قابلة للتكرار بلا تكرار).`
          : `Loaded ${total} realistic sample records (idempotent — safe to re-run).`,
      );
    } catch (e) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg || (isAr ? 'فشل تحميل البيانات' : 'Failed to load sample data'));
    } finally {
      setLoadingSamples(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <Compass size={22} className="text-blue-600" />
            {isAr ? 'تدفقات العرض والإرشادات' : 'Guided Demo Flows'}
          </h1>
          <p className="text-slate-500 mt-1 max-w-2xl">
            {isAr
              ? 'ثلاثة تدفقات جاهزة تعرض الرحلة الكاملة من التنظيم إلى الإجراء. لكل تدفق خطوات مرقمة وروابط مباشرة إلى الصفحات المناسبة.'
              : 'Three ready-made flows that show the end-to-end journey from regulation to action. Each flow lists numbered steps with direct links to the matching screens.'}
          </p>
        </div>
        {canSeed && (
          <div className="flex flex-col items-end gap-2">
            <Button onClick={handleLoadSamples} disabled={loadingSamples} className="gap-2">
              <PlayCircle size={16} />
              {loadingSamples
                ? isAr
                  ? 'جاري التحميل…'
                  : 'Loading…'
                : isAr
                  ? 'تحميل بيانات واقعية (SAMA / CMA / هيئة التأمين)'
                  : 'Load realistic sample data (SAMA / CMA / IA)'}
            </Button>
            {result && <p className="text-xs text-green-700 max-w-xs text-end">{result}</p>}
            {error && (
              <p className="text-xs text-red-600 max-w-xs text-end flex items-center gap-1">
                <AlertTriangle size={12} /> {error}
              </p>
            )}
          </div>
        )}
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-32">
          <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : flows.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-slate-500">
            {isAr ? 'لا توجد تدفقات عرض متاحة.' : 'No demo flows available.'}
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {flows.map((flow) => (
            <Card key={flow.key} className="flex flex-col">
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className="uppercase text-xs">
                    {flow.key}
                  </Badge>
                </div>
                <CardTitle className="text-lg mt-2">
                  {isAr ? flow.title_ar : flow.title_en}
                </CardTitle>
                <p className="text-sm text-slate-500 mt-1">
                  {isAr ? flow.description_ar : flow.description_en}
                </p>
              </CardHeader>
              <CardContent className="flex-1 flex flex-col">
                <ol className="space-y-3 flex-1">
                  {flow.steps.map((step, idx) => (
                    <li key={idx} className="flex gap-3">
                      <div className="shrink-0 w-7 h-7 rounded-full bg-blue-100 text-blue-700 text-sm font-semibold flex items-center justify-center">
                        {idx + 1}
                      </div>
                      <div className="flex-1">
                        <Link
                          to={step.path}
                          onClick={() => handleFlowOpen(flow)}
                          className="text-slate-800 font-medium hover:text-blue-600 inline-flex items-center gap-1"
                        >
                          {isAr ? step.title_ar : step.title_en}
                          <ArrowRight size={14} />
                        </Link>
                        <p className="text-xs text-slate-500 mt-0.5">
                          {isAr ? step.hint_ar : step.hint_en}
                        </p>
                      </div>
                    </li>
                  ))}
                </ol>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Card className="bg-blue-50/40 border-blue-200">
        <CardContent className="py-4 text-sm text-slate-700 leading-6">
          <p className="font-medium text-blue-900 mb-1">
            {isAr ? 'ملاحظة' : 'Tip'}
          </p>
          <p>
            {isAr
              ? 'يمكن تشغيل زر "تحميل بيانات واقعية" عدة مرات بأمان — السيناريوهات محفوظة بمفاتيح ثابتة ولن تتكرر.'
              : 'The "Load realistic sample data" button is safe to run multiple times — scenarios are keyed and will not duplicate.'}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
