import { useState, useEffect } from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Shield, AlertTriangle, CheckCircle, TrendingDown, ArrowRight,
  BarChart3, AlertOctagon, Wrench, Target, ClipboardList, Zap, Clock,
} from 'lucide-react';
import { Link } from 'react-router-dom';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface TopAction {
  id: string;
  title: string;
  title_ar?: string;
  priority: string;
  status: string;
  source_type: string;
  owner?: string;
  due_date?: string;
}

interface ActionCenter {
  total: number;
  open: number;
  overdue: number;
  critical: number;
  completed: number;
  by_priority: Record<string, number>;
  by_source: Record<string, number>;
  top_actions: TopAction[];
}

interface DashboardData {
  generated_at: string;
  risk_register: { total: number; high_risks: number; deteriorating: number; avg_residual_score: number };
  issues: { total: number; open: number; critical_open: number; overdue: number };
  remediation: { total: number; blocked: number; overdue: number; avg_progress_pct: number };
  audit: {
    total_plans: number; active_plans: number; total_engagements: number; open_engagements: number;
    total_findings: number; open_findings: number; critical_findings: number; overdue_findings: number;
    findings_by_severity: Record<string, number>; total_tests: number; ineffective_tests: number;
    overdue_responses: number;
  };
  action_center?: ActionCenter;
  regulatory_backbone: { obligations: number; controls: number; evidence: number };
  exposure_areas: Array<{ area: string; area_ar: string; count: number; details: unknown }>;
  recommended_actions: Array<{ priority: string; action: string; action_ar: string; category: string }>;
  operating_chain: string;
}

export default function GRCDashboardPage() {
  const { t, language } = useLanguage();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = localStorage.getItem('token');
    fetch(`${API}/api/grc/dashboard`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => {
        if (!r.ok) throw new Error(`Dashboard API returned ${r.status}`);
        return r.json();
      })
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load dashboard'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="flex items-center justify-center h-64"><div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" /></div>;

  if (error) return (
    <div className="text-center py-12">
      <AlertTriangle size={32} className="mx-auto mb-2 text-red-400" />
      <p className="text-red-600 font-medium">{language === 'ar' ? 'خطأ في تحميل لوحة المعلومات' : 'Failed to load dashboard'}</p>
      <p className="text-sm text-slate-500 mt-1">{error}</p>
    </div>
  );

  if (!data) return <div className="text-center py-12 text-slate-500">{t('common.no_data')}</div>;

  const priorityColor = (p: string) => {
    switch (p) {
      case 'critical': return 'bg-red-100 text-red-800 border-red-200';
      case 'high': return 'bg-orange-100 text-orange-800 border-orange-200';
      case 'medium': return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      default: return 'bg-blue-100 text-blue-800 border-blue-200';
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900">
          {language === 'ar' ? 'مركز قيادة الحوكمة والمخاطر والامتثال' : 'GRC Command Center'}
        </h1>
        <p className="text-slate-500 mt-1">
          {language === 'ar' ? 'ملخص تنفيذي — أين نحن مكشوفون، ولماذا، وماذا نفعل الآن' : 'Executive Summary — Where are we exposed, why, and what to do now'}
        </p>
      </div>

      {/* Operating Chain Banner */}
      <Card className="bg-gradient-to-r from-slate-800 to-slate-900 text-white">
        <CardContent className="py-3 px-4">
          <div className="flex items-center gap-2 text-sm">
            <Target size={16} className="text-blue-400" />
            <span className="font-medium">{language === 'ar' ? 'سلسلة التشغيل:' : 'Operating Chain:'}</span>
            <span className="text-slate-300">{data.operating_chain}</span>
          </div>
        </CardContent>
      </Card>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-500">{language === 'ar' ? 'إجمالي المخاطر' : 'Total Risks'}</p>
                <p className="text-3xl font-bold text-slate-900">{data.risk_register.total}</p>
                <div className="flex gap-2 mt-2">
                  <Badge variant="destructive" className="text-xs">{data.risk_register.high_risks} {language === 'ar' ? 'عالية' : 'high'}</Badge>
                  {data.risk_register.deteriorating > 0 && (
                    <Badge variant="outline" className="text-xs text-orange-600 border-orange-300">
                      <TrendingDown size={12} className="me-1" />{data.risk_register.deteriorating}
                    </Badge>
                  )}
                </div>
              </div>
              <Shield className="text-blue-500" size={36} />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-500">{language === 'ar' ? 'المشاكل المفتوحة' : 'Open Issues'}</p>
                <p className="text-3xl font-bold text-slate-900">{data.issues.open}</p>
                <div className="flex gap-2 mt-2">
                  {data.issues.critical_open > 0 && <Badge variant="destructive" className="text-xs">{data.issues.critical_open} {language === 'ar' ? 'حرجة' : 'critical'}</Badge>}
                  {data.issues.overdue > 0 && <Badge variant="outline" className="text-xs text-red-600 border-red-300">{data.issues.overdue} {language === 'ar' ? 'متأخرة' : 'overdue'}</Badge>}
                </div>
              </div>
              <AlertTriangle className="text-orange-500" size={36} />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-500">{language === 'ar' ? 'إجراءات العلاج' : 'Remediation Actions'}</p>
                <p className="text-3xl font-bold text-slate-900">{data.remediation.total}</p>
                <div className="flex gap-2 mt-2">
                  {data.remediation.blocked > 0 && <Badge variant="outline" className="text-xs text-red-600 border-red-300">{data.remediation.blocked} {language === 'ar' ? 'محظور' : 'blocked'}</Badge>}
                  <Badge variant="outline" className="text-xs">{data.remediation.avg_progress_pct}% {language === 'ar' ? 'متوسط' : 'avg'}</Badge>
                </div>
              </div>
              <Wrench className="text-purple-500" size={36} />
            </div>
          </CardContent>
        </Card>

        {/* Audit Card */}
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-500">{language === 'ar' ? 'التدقيق الداخلي' : 'Internal Audit'}</p>
                <p className="text-3xl font-bold text-slate-900">{data.audit?.open_findings || 0}</p>
                <div className="flex gap-2 mt-2">
                  {(data.audit?.critical_findings || 0) > 0 && <Badge variant="destructive" className="text-xs">{data.audit.critical_findings} {language === 'ar' ? 'حرجة' : 'critical'}</Badge>}
                  {(data.audit?.overdue_findings || 0) > 0 && <Badge variant="outline" className="text-xs text-red-600 border-red-300">{data.audit.overdue_findings} {language === 'ar' ? 'متأخرة' : 'overdue'}</Badge>}
                  <Badge variant="outline" className="text-xs">{data.audit?.open_engagements || 0} {language === 'ar' ? 'مهام مفتوحة' : 'open eng.'}</Badge>
                </div>
              </div>
              <ClipboardList className="text-indigo-500" size={36} />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-500">{language === 'ar' ? 'العمود الفقري التنظيمي' : 'Regulatory Backbone'}</p>
                <div className="mt-1 space-y-1">
                  <p className="text-sm"><span className="font-semibold">{data.regulatory_backbone.obligations}</span> {language === 'ar' ? 'التزام' : 'obligations'}</p>
                  <p className="text-sm"><span className="font-semibold">{data.regulatory_backbone.controls}</span> {language === 'ar' ? 'ضابط' : 'controls'}</p>
                  <p className="text-sm"><span className="font-semibold">{data.regulatory_backbone.evidence}</span> {language === 'ar' ? 'دليل' : 'evidence'}</p>
                </div>
              </div>
              <BarChart3 className="text-green-500" size={36} />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Action Center Card */}
      {data.action_center && (
        <Card className="border-blue-200">
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Zap size={20} className="text-blue-500" />
                {language === 'ar' ? 'مركز الإجراءات' : 'Action Center'}
              </div>
              <Link to="/grc/actions" className="text-sm text-blue-600 hover:underline font-normal">
                {language === 'ar' ? 'عرض الكل →' : 'View All →'}
              </Link>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-4 gap-4 mb-4">
              <div className="text-center">
                <p className="text-2xl font-bold text-blue-600">{data.action_center.open}</p>
                <p className="text-xs text-slate-500">{language === 'ar' ? 'مفتوح' : 'Open'}</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-red-600">{data.action_center.overdue}</p>
                <p className="text-xs text-slate-500">{language === 'ar' ? 'متأخر' : 'Overdue'}</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-orange-600">{data.action_center.critical}</p>
                <p className="text-xs text-slate-500">{language === 'ar' ? 'حرج' : 'Critical'}</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-green-600">{data.action_center.completed}</p>
                <p className="text-xs text-slate-500">{language === 'ar' ? 'مكتمل' : 'Completed'}</p>
              </div>
            </div>

            {/* Top 3 Actions */}
            {data.action_center.top_actions && data.action_center.top_actions.length > 0 && (
              <div>
                <h4 className="text-sm font-semibold text-slate-700 mb-2">
                  {language === 'ar' ? 'الإجراءات الأكثر إلحاحاً' : 'Most Urgent Actions'}
                </h4>
                <div className="space-y-2">
                  {data.action_center.top_actions.map((action, idx) => (
                    <div key={idx} className={`border rounded-lg p-3 ${priorityColor(action.priority)}`}>
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <Badge className={`text-xs shrink-0 ${
                              action.priority === 'critical' ? 'bg-red-600 text-white' :
                              action.priority === 'high' ? 'bg-orange-600 text-white' :
                              action.priority === 'medium' ? 'bg-yellow-600 text-white' : 'bg-blue-600 text-white'
                            }`}>
                              {action.priority.toUpperCase()}
                            </Badge>
                            <span className="text-sm font-medium">
                              {language === 'ar' && action.title_ar ? action.title_ar : action.title}
                            </span>
                          </div>
                          <div className="flex items-center gap-3 mt-1 text-xs text-slate-500">
                            <span>{action.source_type}</span>
                            {action.owner && <span>{action.owner}</span>}
                            {action.due_date && (
                              <span className="flex items-center gap-1">
                                <Clock size={10} />
                                {action.due_date.split('T')[0]}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* By Priority Bar */}
            {Object.keys(data.action_center.by_priority).length > 0 && (
              <div className="mt-4">
                <h4 className="text-xs font-semibold text-slate-500 mb-1">{language === 'ar' ? 'حسب الأولوية' : 'By Priority'}</h4>
                <div className="flex gap-2">
                  {Object.entries(data.action_center.by_priority).map(([prio, count]) => (
                    <Badge key={prio} variant="outline" className="text-xs">{prio}: {count}</Badge>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Exposure Areas + Recommended Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Where & Why */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertOctagon size={20} className="text-red-500" />
              {language === 'ar' ? 'أين ولماذا نحن مكشوفون؟' : 'Where & Why Are We Exposed?'}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {data.exposure_areas.length === 0 ? (
              <div className="text-center py-8 text-slate-400">
                <CheckCircle size={32} className="mx-auto mb-2 text-green-400" />
                <p>{language === 'ar' ? 'لا توجد مناطق تعرض مفتوحة' : 'No open exposure areas'}</p>
              </div>
            ) : (
              <div className="space-y-4">
                {data.exposure_areas.map((area, idx) => (
                  <div key={idx} className="border rounded-lg p-4">
                    <div className="flex items-center justify-between mb-2">
                      <h4 className="font-semibold text-slate-800">{language === 'ar' ? area.area_ar : area.area}</h4>
                      <Badge variant="destructive">{area.count}</Badge>
                    </div>
                    {area.details && typeof area.details === 'object' ? (
                      <div className="flex flex-wrap gap-2 mt-2">
                        {Array.isArray(area.details) ? (
                          (area.details as Array<{ category?: string; count?: number }>).map((d: { category?: string; count?: number }, i: number) => (
                            <Badge key={i} variant="outline" className="text-xs">{d.category}: {d.count}</Badge>
                          ))
                        ) : (
                          Object.entries(area.details as Record<string, number>).map(([k, v]) => (
                            <Badge key={k} variant="outline" className="text-xs">{k}: {String(v)}</Badge>
                          ))
                        )}
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* What to do now */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ArrowRight size={20} className="text-blue-500" />
              {language === 'ar' ? 'ماذا نفعل الآن؟' : 'What Should We Do Now?'}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {data.recommended_actions.length === 0 ? (
              <div className="text-center py-8 text-slate-400">
                <CheckCircle size={32} className="mx-auto mb-2 text-green-400" />
                <p>{language === 'ar' ? 'لا توجد إجراءات موصى بها' : 'No recommended actions'}</p>
              </div>
            ) : (
              <div className="space-y-3">
                {data.recommended_actions.map((action, idx) => (
                  <div key={idx} className={`border rounded-lg p-3 ${priorityColor(action.priority)}`}>
                    <div className="flex items-start gap-3">
                      <Badge className={`text-xs shrink-0 ${
                        action.priority === 'critical' ? 'bg-red-600' :
                        action.priority === 'high' ? 'bg-orange-600' :
                        action.priority === 'medium' ? 'bg-yellow-600' : 'bg-blue-600'
                      }`}>
                        {action.priority.toUpperCase()}
                      </Badge>
                      <div>
                        <p className="text-sm font-medium">{language === 'ar' ? action.action_ar : action.action}</p>
                        <p className="text-xs mt-1 opacity-70">{action.category}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Footer */}
      <div className="text-xs text-slate-400 text-center">
        {language === 'ar' ? 'تم التوليد في' : 'Generated at'}: {new Date(data.generated_at).toLocaleString()}
        {' | '}
        {language === 'ar' ? 'البيانات مباشرة من النظام — لا توجد بيانات مُصطنعة' : 'Live system data — no fabricated data'}
      </div>
    </div>
  );
}
