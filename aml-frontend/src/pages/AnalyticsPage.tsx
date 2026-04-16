import { useEffect, useState } from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import api from '@/services/api';
import { BarChart3, Brain, TrendingUp, Target, Clock, AlertTriangle, CheckCircle } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line, RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis, AreaChart, Area } from 'recharts';

interface PatternDetection {
  id: string;
  pattern_type: string;
  description: string;
  severity: string;
  entity_ids: string[];
  confidence: number;
  detected_at: string;
  status: string;
}

export default function AnalyticsPage() {
  const { t } = useLanguage();
  const [patterns, setPatterns] = useState<PatternDetection[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/api/loops/patterns').catch(() => ({ data: [] })).then(res => {
      setPatterns(Array.isArray(res.data) ? res.data : []);
    }).finally(() => setLoading(false));
  }, []);

  // Simulated analytics data for demonstration
  const decisionAccuracy = [
    { month: 'Jan', accuracy: 72, falsePositive: 28, speed: 55 },
    { month: 'Feb', accuracy: 74, falsePositive: 26, speed: 52 },
    { month: 'Mar', accuracy: 76, falsePositive: 24, speed: 48 },
    { month: 'Apr', accuracy: 78, falsePositive: 22, speed: 45 },
    { month: 'May', accuracy: 80, falsePositive: 20, speed: 42 },
    { month: 'Jun', accuracy: 82, falsePositive: 18, speed: 38 },
  ];

  const loopEffectiveness = [
    { loop: 'Learning', current: 78, target: 90, baseline: 60 },
    { loop: 'Trust', current: 65, target: 80, baseline: 45 },
    { loop: 'Efficiency', current: 92, target: 95, baseline: 70 },
    { loop: 'Compliance', current: 97, target: 99, baseline: 80 },
  ];

  const radarData = [
    { metric: 'Decision Quality', value: 82 },
    { metric: 'FP Reduction', value: 78 },
    { metric: 'Resolution Speed', value: 88 },
    { metric: 'Audit Readiness', value: 97 },
    { metric: 'AI Acceptance', value: 65 },
    { metric: 'SLA Compliance', value: 92 },
  ];

  const resolutionTrend = [
    { week: 'W1', avgMinutes: 60, cases: 8 },
    { week: 'W2', avgMinutes: 55, cases: 12 },
    { week: 'W3', avgMinutes: 48, cases: 10 },
    { week: 'W4', avgMinutes: 45, cases: 15 },
    { week: 'W5', avgMinutes: 42, cases: 11 },
    { week: 'W6', avgMinutes: 38, cases: 14 },
    { week: 'W7', avgMinutes: 35, cases: 9 },
    { week: 'W8', avgMinutes: 33, cases: 13 },
  ];

  const patternSeverity: Record<string, string> = {
    low: 'secondary', medium: 'warning', high: 'danger', critical: 'destructive',
  };

  const patternTypes: Record<string, string> = {
    ownership_cluster: 'Ownership Cluster',
    repeated_behavior: 'Repeated Behavior',
    high_risk_cluster: 'High-Risk Cluster',
    geographic_concentration: 'Geographic Concentration',
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">{t('analytics.title')}</h1>
        <p className="text-slate-500 text-sm">System Performance, Patterns & Outcome Optimization</p>
      </div>

      {/* Key Outcome Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="bg-green-50 p-3 rounded-xl"><Target className="text-green-600" size={24} /></div>
              <div>
                <p className="text-sm text-slate-500">Decision Accuracy</p>
                <p className="text-2xl font-bold">82%</p>
                <p className="text-xs text-green-600">↑ 10% from baseline</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="bg-blue-50 p-3 rounded-xl"><TrendingUp className="text-blue-600" size={24} /></div>
              <div>
                <p className="text-sm text-slate-500">FP Rate Reduction</p>
                <p className="text-2xl font-bold">18%</p>
                <p className="text-xs text-blue-600">↓ from 28% baseline</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="bg-purple-50 p-3 rounded-xl"><Clock className="text-purple-600" size={24} /></div>
              <div>
                <p className="text-sm text-slate-500">Avg Resolution Time</p>
                <p className="text-2xl font-bold">33min</p>
                <p className="text-xs text-purple-600">↓ from 60min baseline</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="bg-amber-50 p-3 rounded-xl"><Brain className="text-amber-600" size={24} /></div>
              <div>
                <p className="text-sm text-slate-500">AI Acceptance Rate</p>
                <p className="text-2xl font-bold">65%</p>
                <p className="text-xs text-amber-600">↑ from 45% baseline</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Charts Row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Decision Accuracy Trend */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Decision Accuracy & FP Trend</CardTitle>
            <CardDescription>Self-improving through Learning Loop</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={280}>
              <AreaChart data={decisionAccuracy}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="month" />
                <YAxis />
                <Tooltip />
                <Area type="monotone" dataKey="accuracy" stroke="#10b981" fill="#d1fae5" name="Accuracy %" />
                <Area type="monotone" dataKey="falsePositive" stroke="#ef4444" fill="#fee2e2" name="False Positive %" />
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* System Health Radar */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">System Health Radar</CardTitle>
            <CardDescription>Overall system performance metrics</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={280}>
              <RadarChart data={radarData}>
                <PolarGrid />
                <PolarAngleAxis dataKey="metric" tick={{ fontSize: 11 }} />
                <PolarRadiusAxis angle={30} domain={[0, 100]} />
                <Radar name="Performance" dataKey="value" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.3} />
              </RadarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* Charts Row 2 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Loop Effectiveness */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Reinforcing Loop Effectiveness</CardTitle>
            <CardDescription>Current vs Target vs Baseline</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={loopEffectiveness}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="loop" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="baseline" fill="#e2e8f0" name="Baseline" radius={[4, 4, 0, 0]} />
                <Bar dataKey="current" fill="#3b82f6" name="Current" radius={[4, 4, 0, 0]} />
                <Bar dataKey="target" fill="#10b981" name="Target" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Resolution Speed Trend */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Resolution Speed Trend</CardTitle>
            <CardDescription>Efficiency Loop driving improvement</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={resolutionTrend}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="week" />
                <YAxis />
                <Tooltip />
                <Line type="monotone" dataKey="avgMinutes" stroke="#8b5cf6" name="Avg Minutes" strokeWidth={2} dot={{ fill: '#8b5cf6' }} />
                <Line type="monotone" dataKey="cases" stroke="#f59e0b" name="Cases" strokeWidth={2} dot={{ fill: '#f59e0b' }} />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* Pattern Detection */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <AlertTriangle size={20} /> Pattern Detection Engine
          </CardTitle>
          <CardDescription>Automatically detected risk patterns across entities</CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-slate-500">{t('common.loading')}</p>
          ) : patterns.length === 0 ? (
            <div className="text-center py-8">
              <BarChart3 size={48} className="mx-auto text-slate-300 mb-3" />
              <p className="text-slate-500">No patterns detected yet. The system learns from data over time.</p>
              <p className="text-sm text-slate-400 mt-1">Add more entities and transactions to enable pattern detection.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {patterns.map(pattern => (
                <div key={pattern.id} className="border rounded-lg p-4 hover:bg-slate-50 transition-colors">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <Badge variant={(patternSeverity[pattern.severity] || 'secondary') as "warning" | "danger" | "destructive" | "secondary"}>
                        {pattern.severity}
                      </Badge>
                      <div>
                        <p className="font-medium text-sm">
                          {patternTypes[pattern.pattern_type] || pattern.pattern_type}
                        </p>
                        <p className="text-sm text-slate-500">{pattern.description}</p>
                      </div>
                    </div>
                    <div className="text-end">
                      <Badge variant="info">{(pattern.confidence * 100).toFixed(0)}% confidence</Badge>
                      <p className="text-xs text-slate-400 mt-1">{new Date(pattern.detected_at).toLocaleString()}</p>
                    </div>
                  </div>
                  {pattern.entity_ids && pattern.entity_ids.length > 0 && (
                    <div className="mt-2 flex gap-1 flex-wrap">
                      <span className="text-xs text-slate-500">Entities:</span>
                      {pattern.entity_ids.map((id, i) => (
                        <span key={i} className="text-xs font-mono bg-slate-100 px-1.5 py-0.5 rounded">{id.slice(0, 8)}</span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* System Loops Summary */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">System Design: Self-Reinforcing Loops</CardTitle>
          <CardDescription>Players → Interactions → Loops → Patterns → Outcomes</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="border rounded-lg p-4 space-y-2">
              <h4 className="font-medium flex items-center gap-2"><Brain size={16} className="text-blue-600" /> Learning Loop</h4>
              <p className="text-sm text-slate-500">Analyst decisions → Stored reasoning → Improved AI suggestions → Better future decisions</p>
              <div className="flex items-center gap-2 mt-2">
                <div className="flex-1 bg-slate-100 rounded-full h-2">
                  <div className="h-full rounded-full bg-blue-500" style={{ width: '78%' }} />
                </div>
                <span className="text-sm font-medium">78%</span>
              </div>
            </div>
            <div className="border rounded-lg p-4 space-y-2">
              <h4 className="font-medium flex items-center gap-2"><CheckCircle size={16} className="text-green-600" /> Trust Loop</h4>
              <p className="text-sm text-slate-500">AI explains → User feedback → Better explanations → Higher trust & adoption</p>
              <div className="flex items-center gap-2 mt-2">
                <div className="flex-1 bg-slate-100 rounded-full h-2">
                  <div className="h-full rounded-full bg-green-500" style={{ width: '65%' }} />
                </div>
                <span className="text-sm font-medium">65%</span>
              </div>
            </div>
            <div className="border rounded-lg p-4 space-y-2">
              <h4 className="font-medium flex items-center gap-2"><Clock size={16} className="text-amber-600" /> Efficiency Loop</h4>
              <p className="text-sm text-slate-500">Time tracking → Bottleneck detection → Workflow optimization → Faster resolution</p>
              <div className="flex items-center gap-2 mt-2">
                <div className="flex-1 bg-slate-100 rounded-full h-2">
                  <div className="h-full rounded-full bg-amber-500" style={{ width: '92%' }} />
                </div>
                <span className="text-sm font-medium">92%</span>
              </div>
            </div>
            <div className="border rounded-lg p-4 space-y-2">
              <h4 className="font-medium flex items-center gap-2"><Target size={16} className="text-purple-600" /> Compliance Strength Loop</h4>
              <p className="text-sm text-slate-500">Audit quality → Decision traceability → Regulatory confidence → Stronger compliance</p>
              <div className="flex items-center gap-2 mt-2">
                <div className="flex-1 bg-slate-100 rounded-full h-2">
                  <div className="h-full rounded-full bg-purple-500" style={{ width: '97%' }} />
                </div>
                <span className="text-sm font-medium">97%</span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
