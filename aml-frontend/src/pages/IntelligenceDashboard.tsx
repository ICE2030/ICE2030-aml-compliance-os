import { useEffect, useState } from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import api from '@/services/api';
import { BarChart, Bar, PieChart, Pie, Cell, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { Brain, TrendingUp, AlertTriangle, Clock, Target, RefreshCw, Layers } from 'lucide-react';

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];

interface DashboardData {
  decision_distribution: Array<{ name: string; value: number }>;
  confidence_distribution: Array<{ range: string; count: number }>;
  fp_trends: Array<{ period: string; fp_rate: number; total_cases: number }>;
  resolution_trends: Array<{ period: string; avg_minutes: number }>;
  ai_usage: {
    acceptance_rate: number;
    override_rate: number;
    avg_confidence_when_accepted: number;
    avg_confidence_when_rejected: number;
    total_suggestions: number;
  };
  loop_health: {
    decision_loop: Record<string, unknown>;
    false_positive_loop: Record<string, unknown>;
    efficiency_loop: Record<string, unknown>;
    trust_loop: Record<string, unknown>;
  };
  active_patterns: Array<{
    id: string;
    cluster_name: string;
    cluster_type: string;
    description: string;
    case_count: number;
    dominant_decision: string;
    severity: string;
  }>;
  consistency_score: number;
  total_decisions: number;
}

export default function IntelligenceDashboard() {
  const { t } = useLanguage();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  const loadDashboard = async () => {
    setLoading(true);
    try {
      const res = await api.get('/api/intelligence/dashboard');
      setData(res.data);
    } catch (err) {
      console.error('Dashboard load error:', err);
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  const runPatternDetection = async () => {
    try {
      await api.post('/api/intelligence/patterns/detect');
      loadDashboard();
    } catch (err) { console.error(err); }
  };

  useEffect(() => { loadDashboard(); }, []);

  if (loading) return <p className="text-slate-500 p-8">{t('common.loading')}</p>;
  if (!data) return (
    <div className="p-8 text-center">
      <p className="text-slate-500 mb-4">{t('intelligence.no_data')}</p>
      <Button onClick={loadDashboard}>{t('common.refresh')}</Button>
    </div>
  );

  const severityColor = (s: string) => {
    if (s === 'high') return 'destructive';
    if (s === 'medium') return 'warning';
    return 'secondary';
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2"><Brain size={24} className="text-purple-600" /> {t('intelligence.title')}</h1>
          <p className="text-slate-500 text-sm">{t('intelligence.subtitle')}</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={runPatternDetection}><Layers size={16} className="me-1" /> {t('intelligence.detect_patterns')}</Button>
          <Button variant="outline" onClick={loadDashboard}><RefreshCw size={16} className="me-1" /> {t('common.refresh')}</Button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-100 rounded-lg"><Target size={20} className="text-blue-600" /></div>
              <div>
                <p className="text-2xl font-bold">{data.total_decisions}</p>
                <p className="text-xs text-slate-500">{t('intelligence.total_decisions')}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-green-100 rounded-lg"><TrendingUp size={20} className="text-green-600" /></div>
              <div>
                <p className="text-2xl font-bold">{(data.consistency_score * 100).toFixed(0)}%</p>
                <p className="text-xs text-slate-500">{t('intelligence.consistency')}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-purple-100 rounded-lg"><Brain size={20} className="text-purple-600" /></div>
              <div>
                <p className="text-2xl font-bold">{(data.ai_usage.acceptance_rate * 100).toFixed(0)}%</p>
                <p className="text-xs text-slate-500">{t('intelligence.ai_acceptance')}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-amber-100 rounded-lg"><AlertTriangle size={20} className="text-amber-600" /></div>
              <div>
                <p className="text-2xl font-bold">{data.active_patterns.length}</p>
                <p className="text-xs text-slate-500">{t('intelligence.active_patterns')}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Charts Row 1 */}
      <div className="grid grid-cols-2 gap-4">
        <Card>
          <CardHeader><CardTitle className="text-base">{t('intelligence.decision_dist')}</CardTitle></CardHeader>
          <CardContent>
            {data.decision_distribution.length > 0 ? (
              <ResponsiveContainer width="100%" height={250}>
                <PieChart>
                  <Pie data={data.decision_distribution} cx="50%" cy="50%" outerRadius={80} dataKey="value" label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
                    {data.decision_distribution.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            ) : <p className="text-sm text-slate-400 text-center py-8">{t('common.no_data')}</p>}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-base">{t('intelligence.confidence_dist')}</CardTitle></CardHeader>
          <CardContent>
            {data.confidence_distribution.length > 0 ? (
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={data.confidence_distribution}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="range" />
                  <YAxis />
                  <Tooltip />
                  <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : <p className="text-sm text-slate-400 text-center py-8">{t('common.no_data')}</p>}
          </CardContent>
        </Card>
      </div>

      {/* Charts Row 2 */}
      <div className="grid grid-cols-2 gap-4">
        <Card>
          <CardHeader><CardTitle className="text-base">{t('intelligence.fp_trends')}</CardTitle></CardHeader>
          <CardContent>
            {data.fp_trends.length > 0 ? (
              <ResponsiveContainer width="100%" height={250}>
                <LineChart data={data.fp_trends}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="period" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Line type="monotone" dataKey="fp_rate" stroke="#ef4444" name={t('intelligence.fp_rate')} />
                  <Line type="monotone" dataKey="total_cases" stroke="#3b82f6" name={t('intelligence.total_cases')} />
                </LineChart>
              </ResponsiveContainer>
            ) : <p className="text-sm text-slate-400 text-center py-8">{t('common.no_data')}</p>}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-base">{t('intelligence.resolution_speed')}</CardTitle></CardHeader>
          <CardContent>
            {data.resolution_trends.length > 0 ? (
              <ResponsiveContainer width="100%" height={250}>
                <LineChart data={data.resolution_trends}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="period" />
                  <YAxis />
                  <Tooltip />
                  <Line type="monotone" dataKey="avg_minutes" stroke="#10b981" name={t('intelligence.avg_minutes')} />
                </LineChart>
              </ResponsiveContainer>
            ) : <p className="text-sm text-slate-400 text-center py-8">{t('common.no_data')}</p>}
          </CardContent>
        </Card>
      </div>

      {/* AI Usage & Loop Health */}
      <div className="grid grid-cols-2 gap-4">
        <Card>
          <CardHeader><CardTitle className="text-base">{t('intelligence.ai_usage')}</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-sm text-slate-600">{t('intelligence.ai_acceptance')}</span>
              <span className="font-bold text-green-600">{(data.ai_usage.acceptance_rate * 100).toFixed(1)}%</span>
            </div>
            <div className="w-full bg-slate-100 rounded-full h-2">
              <div className="bg-green-500 rounded-full h-2" style={{ width: `${data.ai_usage.acceptance_rate * 100}%` }} />
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-slate-600">{t('intelligence.ai_override')}</span>
              <span className="font-bold text-amber-600">{(data.ai_usage.override_rate * 100).toFixed(1)}%</span>
            </div>
            <div className="w-full bg-slate-100 rounded-full h-2">
              <div className="bg-amber-500 rounded-full h-2" style={{ width: `${data.ai_usage.override_rate * 100}%` }} />
            </div>
            <div className="grid grid-cols-2 gap-4 pt-2 text-sm">
              <div className="bg-slate-50 rounded p-2">
                <p className="text-slate-500">{t('intelligence.conf_accepted')}</p>
                <p className="font-bold">{(data.ai_usage.avg_confidence_when_accepted * 100).toFixed(0)}%</p>
              </div>
              <div className="bg-slate-50 rounded p-2">
                <p className="text-slate-500">{t('intelligence.conf_rejected')}</p>
                <p className="font-bold">{(data.ai_usage.avg_confidence_when_rejected * 100).toFixed(0)}%</p>
              </div>
            </div>
            <p className="text-xs text-slate-400">{t('intelligence.total_suggestions')}: {data.ai_usage.total_suggestions}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-base flex items-center gap-2"><Clock size={16} /> {t('intelligence.loop_health')}</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {Object.entries(data.loop_health).map(([key, val]) => (
              <div key={key} className="bg-slate-50 rounded-lg p-3">
                <h5 className="text-sm font-medium capitalize mb-1">{key.replace('_', ' ')}</h5>
                <div className="text-xs text-slate-600 space-y-1">
                  {Object.entries(val as Record<string, unknown>).slice(0, 3).map(([k, v]) => (
                    <div key={k} className="flex justify-between">
                      <span>{k.replace(/_/g, ' ')}</span>
                      <span className="font-medium">{typeof v === 'number' ? (v < 1 ? `${(v * 100).toFixed(1)}%` : v.toFixed(1)) : String(v)}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      {/* Active Patterns */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2"><Layers size={16} /> {t('intelligence.patterns')}</CardTitle>
        </CardHeader>
        <CardContent>
          {data.active_patterns.length === 0 ? (
            <p className="text-sm text-slate-400 text-center py-4">{t('intelligence.no_patterns')}</p>
          ) : (
            <div className="space-y-3">
              {data.active_patterns.map(p => (
                <div key={p.id} className="border rounded-lg p-3 flex items-start justify-between">
                  <div>
                    <h5 className="font-medium text-sm">{p.cluster_name}</h5>
                    <p className="text-xs text-slate-500 mt-1">{p.description}</p>
                    <div className="flex gap-3 mt-1 text-xs text-slate-600">
                      <span>{t('intelligence.cases')}: {p.case_count}</span>
                      <span>{t('case.decision')}: <span className="capitalize">{p.dominant_decision.replace('_', ' ')}</span></span>
                      <span>{t('intelligence.type')}: {p.cluster_type}</span>
                    </div>
                  </div>
                  <Badge variant={severityColor(p.severity) as "destructive" | "warning" | "secondary"}>{p.severity}</Badge>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
