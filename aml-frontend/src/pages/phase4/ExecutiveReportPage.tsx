import { useState, useEffect } from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import api from '@/services/api';
import { Button } from '@/components/ui/button';
import { BarChart3, RefreshCw, AlertTriangle, Shield, FileText, CheckCircle } from 'lucide-react';
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts';

interface ExecReport {
  generated_at: string;
  overview: {
    total_obligations: number;
    mapped_obligations: number;
    unmapped_obligations: number;
    control_coverage_pct: number;
    total_controls: number;
    total_evidence: number;
    evidence_coverage_pct: number;
  };
  risk_summary: {
    by_severity: Record<string, number>;
    avg_risk_score: number;
    high_risk_count: number;
  };
  by_regulator: Array<{
    regulator: string;
    total_obligations: number;
    mapped: number;
    unmapped: number;
    coverage_pct: number;
    high_risk: number;
  }>;
  by_obligation_type: Record<string, number>;
  by_review_status: Record<string, number>;
  top_gaps: Array<{
    obligation_text: string;
    risk_severity: string;
    risk_score: number;
    regulator?: string;
  }>;
  recommendations: Array<{
    priority: string;
    category: string;
    text: string;
    text_ar: string;
  }>;
}

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4'];
const SEVERITY_COLORS: Record<string, string> = {
  critical: '#dc2626', high: '#f97316', medium: '#eab308', low: '#22c55e',
};

export default function ExecutiveReportPage() {
  const { t, language } = useLanguage();
  const [report, setReport] = useState<ExecReport | null>(null);
  const [loading, setLoading] = useState(true);

  const loadReport = async () => {
    setLoading(true);
    try {
      const res = await api.get('/api/phase4/reports/executive');
      setReport(res.data);
    } catch { /* ignore */ }
    setLoading(false);
  };

  useEffect(() => { loadReport(); }, []);

  if (loading) {
    return (
      <div className="text-center py-20 text-slate-400">
        <RefreshCw className="mx-auto animate-spin" size={32} />
        <p className="mt-3">{t('common.loading')}</p>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="text-center py-20">
        <BarChart3 className="mx-auto text-slate-300" size={48} />
        <p className="text-slate-500 mt-3">{t('p4.no_report_data')}</p>
        <Button onClick={loadReport} className="mt-4">{t('p4.refresh')}</Button>
      </div>
    );
  }

  const ov = report.overview;
  const riskData = Object.entries(report.risk_summary.by_severity || {}).map(([key, val]) => ({
    name: t(`p4.severity_${key}`), value: val, fill: SEVERITY_COLORS[key] || '#94a3b8',
  }));
  const typeData = Object.entries(report.by_obligation_type || {}).map(([key, val], i) => ({
    name: key, value: val, fill: COLORS[i % COLORS.length],
  }));
  const reviewData = Object.entries(report.by_review_status || {}).map(([key, val], i) => ({
    name: key, value: val, fill: COLORS[i % COLORS.length],
  }));
  const regulatorData = (report.by_regulator || []).map(r => ({
    name: r.regulator || 'Unknown',
    mapped: r.mapped,
    unmapped: r.unmapped,
    high_risk: r.high_risk,
    coverage: r.coverage_pct,
  }));

  const priorityColors: Record<string, string> = {
    critical: 'border-red-500 bg-red-50', high: 'border-orange-500 bg-orange-50',
    medium: 'border-amber-500 bg-amber-50', low: 'border-green-500 bg-green-50',
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <BarChart3 className="text-indigo-600" size={28} />
            {t('p4.exec_title')}
          </h1>
          <p className="text-slate-500 mt-1">{t('p4.exec_subtitle')}</p>
        </div>
        <div className="flex gap-2 items-center">
          <span className="text-xs text-slate-400">
            {t('p4.generated_at')}: {new Date(report.generated_at).toLocaleString(language === 'ar' ? 'ar-SA' : 'en-US')}
          </span>
          <Button variant="outline" size="sm" onClick={loadReport} className="gap-1">
            <RefreshCw size={14} /> {t('p4.refresh')}
          </Button>
        </div>
      </div>

      {/* Overview KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border p-5">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-blue-100 flex items-center justify-center">
              <FileText className="text-blue-600" size={20} />
            </div>
            <div>
              <p className="text-2xl font-bold text-slate-900">{ov.total_obligations}</p>
              <p className="text-xs text-slate-500">{t('p4.total_obligations')}</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl border p-5">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-green-100 flex items-center justify-center">
              <Shield className="text-green-600" size={20} />
            </div>
            <div>
              <p className="text-2xl font-bold text-green-600">{ov.control_coverage_pct.toFixed(0)}%</p>
              <p className="text-xs text-slate-500">{t('p4.control_coverage')}</p>
            </div>
          </div>
          <div className="mt-2 h-2 bg-slate-100 rounded-full">
            <div className="h-2 bg-green-500 rounded-full" style={{ width: `${Math.min(ov.control_coverage_pct, 100)}%` }} />
          </div>
        </div>
        <div className="bg-white rounded-xl border p-5">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-teal-100 flex items-center justify-center">
              <CheckCircle className="text-teal-600" size={20} />
            </div>
            <div>
              <p className="text-2xl font-bold text-teal-600">{ov.evidence_coverage_pct.toFixed(0)}%</p>
              <p className="text-xs text-slate-500">{t('p4.evidence_coverage')}</p>
            </div>
          </div>
          <div className="mt-2 h-2 bg-slate-100 rounded-full">
            <div className="h-2 bg-teal-500 rounded-full" style={{ width: `${Math.min(ov.evidence_coverage_pct, 100)}%` }} />
          </div>
        </div>
        <div className="bg-white rounded-xl border p-5">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-red-100 flex items-center justify-center">
              <AlertTriangle className="text-red-600" size={20} />
            </div>
            <div>
              <p className="text-2xl font-bold text-red-600">{report.risk_summary.high_risk_count}</p>
              <p className="text-xs text-slate-500">{t('p4.high_risk_items')}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Risk severity pie */}
        <div className="bg-white rounded-xl border p-5">
          <h3 className="font-semibold text-slate-800 mb-4">{t('p4.risk_distribution')}</h3>
          {riskData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie data={riskData} cx="50%" cy="50%" outerRadius={90} dataKey="value" label={({ name, value }) => `${name}: ${value}`}>
                  {riskData.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-center text-slate-400 py-12">{t('p4.no_risk_data')}</p>
          )}
        </div>

        {/* By regulator bar */}
        <div className="bg-white rounded-xl border p-5">
          <h3 className="font-semibold text-slate-800 mb-4">{t('p4.by_regulator')}</h3>
          {regulatorData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={regulatorData}>
                <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Legend />
                <Bar dataKey="mapped" fill="#22c55e" name={t('p4.mapped')} stackId="a" />
                <Bar dataKey="unmapped" fill="#ef4444" name={t('p4.unmapped')} stackId="a" />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-center text-slate-400 py-12">{t('common.no_data')}</p>
          )}
        </div>

        {/* Obligation type pie */}
        <div className="bg-white rounded-xl border p-5">
          <h3 className="font-semibold text-slate-800 mb-4">{t('p4.by_obligation_type')}</h3>
          {typeData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie data={typeData} cx="50%" cy="50%" outerRadius={90} dataKey="value" label={({ name, value }) => `${name}: ${value}`}>
                  {typeData.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-center text-slate-400 py-12">{t('common.no_data')}</p>
          )}
        </div>

        {/* Review status pie */}
        <div className="bg-white rounded-xl border p-5">
          <h3 className="font-semibold text-slate-800 mb-4">{t('p4.by_review_status')}</h3>
          {reviewData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie data={reviewData} cx="50%" cy="50%" outerRadius={90} dataKey="value" label={({ name, value }) => `${name}: ${value}`}>
                  {reviewData.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-center text-slate-400 py-12">{t('common.no_data')}</p>
          )}
        </div>
      </div>

      {/* Top gaps */}
      {report.top_gaps && report.top_gaps.length > 0 && (
        <div className="bg-white rounded-xl border p-5">
          <h3 className="font-semibold text-slate-800 mb-4">{t('p4.top_gaps')}</h3>
          <div className="space-y-2">
            {report.top_gaps.slice(0, 10).map((gap, idx) => (
              <div key={idx} className="flex items-start gap-3 p-3 bg-slate-50 rounded-lg">
                <span className="text-xs font-bold text-slate-400 mt-0.5">#{idx + 1}</span>
                <div className="flex-1">
                  <p className="text-sm text-slate-800">{gap.obligation_text?.substring(0, 200)}</p>
                  <div className="flex gap-2 mt-1">
                    {gap.regulator && <span className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded">{gap.regulator}</span>}
                    <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                      gap.risk_severity === 'critical' ? 'bg-red-100 text-red-700' :
                      gap.risk_severity === 'high' ? 'bg-orange-100 text-orange-700' :
                      'bg-amber-100 text-amber-700'
                    }`}>
                      {t(`p4.severity_${gap.risk_severity}`)} ({(gap.risk_score * 100).toFixed(0)}%)
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recommendations */}
      {report.recommendations && report.recommendations.length > 0 && (
        <div className="bg-white rounded-xl border p-5">
          <h3 className="font-semibold text-slate-800 mb-4">{t('p4.recommendations')}</h3>
          <div className="space-y-3">
            {report.recommendations.map((rec, idx) => (
              <div key={idx} className={`p-4 rounded-lg border-s-4 ${priorityColors[rec.priority] || 'border-slate-300 bg-slate-50'}`}>
                <div className="flex items-center gap-2 mb-1">
                  <span className={`text-xs font-bold uppercase ${
                    rec.priority === 'critical' ? 'text-red-600' :
                    rec.priority === 'high' ? 'text-orange-600' :
                    rec.priority === 'medium' ? 'text-amber-600' : 'text-green-600'
                  }`}>
                    {t(`p4.priority_${rec.priority}`)}
                  </span>
                  <span className="text-xs text-slate-400">• {rec.category}</span>
                </div>
                <p className="text-sm text-slate-800">
                  {language === 'ar' ? rec.text_ar : rec.text}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Regulator details table */}
      {report.by_regulator && report.by_regulator.length > 0 && (
        <div className="bg-white rounded-xl border p-5">
          <h3 className="font-semibold text-slate-800 mb-4">{t('p4.regulator_details')}</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-slate-500">
                  <th className="text-start py-2 px-3">{t('p4.regulator')}</th>
                  <th className="text-center py-2 px-3">{t('p4.total_obligations')}</th>
                  <th className="text-center py-2 px-3">{t('p4.mapped')}</th>
                  <th className="text-center py-2 px-3">{t('p4.unmapped')}</th>
                  <th className="text-center py-2 px-3">{t('p4.coverage')}</th>
                  <th className="text-center py-2 px-3">{t('p4.gap_high_risk')}</th>
                </tr>
              </thead>
              <tbody>
                {report.by_regulator.map((r, idx) => (
                  <tr key={idx} className="border-b last:border-0">
                    <td className="py-2 px-3 font-medium">{r.regulator}</td>
                    <td className="text-center py-2 px-3">{r.total_obligations}</td>
                    <td className="text-center py-2 px-3 text-green-600">{r.mapped}</td>
                    <td className="text-center py-2 px-3 text-red-600">{r.unmapped}</td>
                    <td className="text-center py-2 px-3">
                      <div className="flex items-center gap-2 justify-center">
                        <div className="w-16 h-2 bg-slate-100 rounded-full">
                          <div className="h-2 bg-green-500 rounded-full" style={{ width: `${Math.min(r.coverage_pct, 100)}%` }} />
                        </div>
                        <span className="text-xs">{r.coverage_pct.toFixed(0)}%</span>
                      </div>
                    </td>
                    <td className="text-center py-2 px-3">
                      {r.high_risk > 0 ? (
                        <span className="bg-red-100 text-red-700 px-2 py-0.5 rounded text-xs font-medium">{r.high_risk}</span>
                      ) : (
                        <span className="text-green-600">0</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
