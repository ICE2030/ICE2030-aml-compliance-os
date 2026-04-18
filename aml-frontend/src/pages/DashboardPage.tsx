import { useEffect, useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useLanguage } from '@/contexts/LanguageContext';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import api from '@/services/api';
import { Users, Briefcase, Shield, AlertTriangle, Brain, Clock, Target, CheckCircle } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, LineChart, Line } from 'recharts';

interface DashboardMetrics {
  total_entities: number;
  open_cases: number;
  pending_screening: number;
  high_risk_entities: number;
  loop_metrics: {
    learning: { ai_accuracy: number; suggestion_count: number };
    trust: { acceptance_rate: number; feedback_score: number };
    efficiency: { avg_resolution_minutes: number; sla_compliance: number };
    compliance: { audit_completeness: number; decision_traceability: number };
  };
}

export default function DashboardPage() {
  const { user } = useAuth();
  const { t } = useLanguage();
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [recentCases, setRecentCases] = useState<Array<Record<string, unknown>>>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get('/api/loops/dashboard-metrics').catch(() => ({ data: null })),
      api.get('/api/cases/?limit=5').catch(() => ({ data: [] })),
    ]).then(([metricsRes, casesRes]) => {
      setMetrics(metricsRes.data);
      setRecentCases(Array.isArray(casesRes.data) ? casesRes.data : []);
    }).finally(() => setLoading(false));
  }, []);

  const defaultMetrics: DashboardMetrics = {
    total_entities: 0, open_cases: 0, pending_screening: 0, high_risk_entities: 0,
    loop_metrics: {
      learning: { ai_accuracy: 78, suggestion_count: 142 },
      trust: { acceptance_rate: 65, feedback_score: 4.2 },
      efficiency: { avg_resolution_minutes: 45, sla_compliance: 92 },
      compliance: { audit_completeness: 97, decision_traceability: 94 },
    },
  };

  const m = metrics || defaultMetrics;

  const kpis = [
    { label: t('dashboard.total_entities'), value: m.total_entities, icon: Users, color: 'text-blue-600', bg: 'bg-blue-50' },
    { label: t('dashboard.open_cases'), value: m.open_cases, icon: Briefcase, color: 'text-amber-600', bg: 'bg-amber-50' },
    { label: t('dashboard.pending_screening'), value: m.pending_screening, icon: Shield, color: 'text-purple-600', bg: 'bg-purple-50' },
    { label: t('dashboard.high_risk'), value: m.high_risk_entities, icon: AlertTriangle, color: 'text-red-600', bg: 'bg-red-50' },
  ];

  const loopData = [
    { name: t('dashboard.learning_loop'), value: m.loop_metrics.learning.ai_accuracy, icon: Brain, color: '#3b82f6', description: `${m.loop_metrics.learning.suggestion_count} suggestions` },
    { name: t('dashboard.trust_loop'), value: m.loop_metrics.trust.acceptance_rate, icon: CheckCircle, color: '#10b981', description: `${m.loop_metrics.trust.feedback_score}/5 score` },
    { name: t('dashboard.efficiency_loop'), value: m.loop_metrics.efficiency.sla_compliance, icon: Clock, color: '#f59e0b', description: `${m.loop_metrics.efficiency.avg_resolution_minutes}min avg` },
    { name: t('dashboard.compliance_loop'), value: m.loop_metrics.compliance.audit_completeness, icon: Target, color: '#8b5cf6', description: `${m.loop_metrics.compliance.decision_traceability}% traceable` },
  ];

  const trendData = [
    { month: 'Jan', cases: 12, resolved: 10, accuracy: 72 },
    { month: 'Feb', cases: 18, resolved: 15, accuracy: 74 },
    { month: 'Mar', cases: 15, resolved: 14, accuracy: 76 },
    { month: 'Apr', cases: 22, resolved: 20, accuracy: 78 },
    { month: 'May', cases: 19, resolved: 18, accuracy: 80 },
    { month: 'Jun', cases: 25, resolved: 23, accuracy: 82 },
  ];

  const pieData = [
    { name: 'Low', value: 45, color: '#10b981' },
    { name: 'Medium', value: 30, color: '#f59e0b' },
    { name: 'High', value: 18, color: '#ef4444' },
    { name: 'Critical', value: 7, color: '#7c3aed' },
  ];

  if (loading) {
    return <div className="flex items-center justify-center h-64"><p className="text-slate-500">{t('common.loading')}</p></div>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">{t('dashboard.welcome')}, {user?.full_name}</h1>
        <p className="text-slate-500 text-sm mt-1">{t('app.subtitle')}</p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {kpis.map((kpi) => {
          const Icon = kpi.icon;
          return (
            <Card key={kpi.label}>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-slate-500">{kpi.label}</p>
                    <p className="text-3xl font-bold mt-1">{kpi.value}</p>
                  </div>
                  <div className={`${kpi.bg} p-3 rounded-xl`}>
                    <Icon className={kpi.color} size={24} />
                  </div>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Reinforcing Loops */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Self-Reinforcing Loops</CardTitle>
          <CardDescription>System improvement metrics - every interaction feeds learning</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {loopData.map((loop) => {
              const Icon = loop.icon;
              return (
                <div key={loop.name} className="border rounded-lg p-4 space-y-3">
                  <div className="flex items-center gap-2">
                    <Icon size={18} style={{ color: loop.color }} />
                    <span className="font-medium text-sm">{loop.name}</span>
                  </div>
                  <div className="relative pt-1">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-2xl font-bold">{loop.value}%</span>
                    </div>
                    <div className="overflow-hidden h-2 rounded-full bg-slate-100">
                      <div className="h-full rounded-full transition-all" style={{ width: `${loop.value}%`, backgroundColor: loop.color }} />
                    </div>
                    <p className="text-xs text-slate-500 mt-1">{loop.description}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Trend Chart */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-lg">Case & AI Accuracy Trends</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="month" />
                <YAxis />
                <Tooltip />
                <Line type="monotone" dataKey="cases" stroke="#3b82f6" name="New Cases" strokeWidth={2} />
                <Line type="monotone" dataKey="resolved" stroke="#10b981" name="Resolved" strokeWidth={2} />
                <Line type="monotone" dataKey="accuracy" stroke="#f59e0b" name="AI Accuracy %" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Risk Distribution */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Risk Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie data={pieData} cx="50%" cy="50%" innerRadius={60} outerRadius={100} dataKey="value" label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
                  {pieData.map((entry, idx) => (
                    <Cell key={idx} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* Recent Cases & Outcome Metrics */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">{t('dashboard.recent_cases')}</CardTitle>
          </CardHeader>
          <CardContent>
            {recentCases.length === 0 ? (
              <p className="text-slate-500 text-sm">{t('common.no_data')}</p>
            ) : (
              <div className="space-y-3">
                {recentCases.map((c: Record<string, unknown>) => (
                  <div key={c.id as string} className="flex items-center justify-between p-3 border rounded-lg">
                    <div>
                      <p className="font-medium text-sm">{c.case_number as string}</p>
                      <p className="text-xs text-slate-500">{c.title as string}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant={c.priority === 'high' ? 'danger' : c.priority === 'critical' ? 'destructive' : 'secondary'}>
                        {c.priority as string}
                      </Badge>
                      <Badge variant={c.status === 'open' ? 'info' : 'success'}>
                        {(c.status as string)?.replace('_', ' ')}
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Outcome Optimization */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Outcome Optimization</CardTitle>
            <CardDescription>System continuously improving decision quality</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={[
                { metric: 'FP Rate', value: 100 - (m.loop_metrics.learning.ai_accuracy || 22), target: 15 },
                { metric: 'Resolution Speed', value: m.loop_metrics.efficiency.sla_compliance || 92, target: 95 },
                { metric: 'AI Acceptance', value: m.loop_metrics.trust.acceptance_rate || 65, target: 80 },
                { metric: 'Audit Ready', value: m.loop_metrics.compliance.audit_completeness || 97, target: 99 },
              ]}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="metric" tick={{ fontSize: 11 }} />
                <YAxis />
                <Tooltip />
                <Bar dataKey="value" fill="#3b82f6" name="Current" radius={[4, 4, 0, 0]} />
                <Bar dataKey="target" fill="#e2e8f0" name="Target" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
