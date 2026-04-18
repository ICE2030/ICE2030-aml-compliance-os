import { useEffect, useState } from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import api from '@/services/api';
import { ShieldAlert, Plus, X, Activity } from 'lucide-react';

interface RiskRule {
  id: string;
  name: string;
  description: string;
  category: string;
  weight: number;
  is_active: boolean;
  conditions: Record<string, unknown>;
}

interface RiskAssessment {
  id: string;
  entity_id: string;
  entity_name?: string;
  total_score: number;
  risk_level: string;
  factor_scores: Record<string, number>;
  override_level: string | null;
  override_reasoning: string | null;
  assessed_by: string;
  created_at: string;
}

const riskColors: Record<string, string> = {
  low: 'success', medium: 'warning', high: 'danger', critical: 'destructive',
};

export default function RiskPage() {
  const { t } = useLanguage();
  const [rules, setRules] = useState<RiskRule[]>([]);
  const [assessments, setAssessments] = useState<RiskAssessment[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'assessments' | 'rules'>('assessments');
  const [showOverride, setShowOverride] = useState<RiskAssessment | null>(null);
  const [overrideForm, setOverrideForm] = useState({ level: '', reasoning: '', confidence: 0.8 });
  const [showRuleForm, setShowRuleForm] = useState(false);
  const [ruleForm, setRuleForm] = useState({
    name: '', description: '', category: 'country', weight: 1.0,
  });
  const [entities, setEntities] = useState<Array<{ id: string; name: string }>>([]);
  const [assessEntityId, setAssessEntityId] = useState('');

  const loadData = () => {
    setLoading(true);
    Promise.all([
      api.get('/api/risk/rules').catch(() => ({ data: [] })),
      api.get('/api/risk/assessments').catch(() => ({ data: [] })),
      api.get('/api/onboarding/entities').catch(() => ({ data: [] })),
    ]).then(([rulesRes, assessRes, entitiesRes]) => {
      setRules(Array.isArray(rulesRes.data) ? rulesRes.data : []);
      setAssessments(Array.isArray(assessRes.data) ? assessRes.data : []);
      setEntities(Array.isArray(entitiesRes.data) ? entitiesRes.data : []);
    }).finally(() => setLoading(false));
  };

  useEffect(() => { loadData(); }, []);

  const assessEntity = async () => {
    if (!assessEntityId) return;
    try {
      await api.post(`/api/risk/assess/${assessEntityId}`);
      loadData();
    } catch (err) { console.error(err); }
  };

  const overrideRisk = async () => {
    if (!showOverride) return;
    try {
      await api.post(`/api/risk/assessments/${showOverride.id}/override`, {
        override_level: overrideForm.level,
        reasoning: overrideForm.reasoning,
        confidence_level: overrideForm.confidence,
      });
      setShowOverride(null);
      loadData();
    } catch (err) { console.error(err); }
  };

  const createRule = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.post('/api/risk/rules', { ...ruleForm, is_active: true, conditions: {} });
      setShowRuleForm(false);
      loadData();
    } catch (err) { console.error(err); }
  };

  const getRiskGradient = (score: number) => {
    if (score < 30) return 'from-green-500 to-green-400';
    if (score < 60) return 'from-yellow-500 to-yellow-400';
    if (score < 80) return 'from-orange-500 to-orange-400';
    return 'from-red-500 to-red-400';
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{t('risk.title')}</h1>
          <p className="text-slate-500 text-sm">Dynamic Risk Scoring & Assessment</p>
        </div>
      </div>

      {/* Assess Entity */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Activity size={20} /> Run Risk Assessment
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-3">
            <Select value={assessEntityId} onChange={e => setAssessEntityId(e.target.value)} className="flex-1">
              <option value="">Select entity to assess...</option>
              {entities.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
            </Select>
            <Button onClick={assessEntity} disabled={!assessEntityId} className="bg-blue-600 hover:bg-blue-700">
              <ShieldAlert size={16} className="me-2" /> Assess Risk
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Tabs */}
      <div className="flex gap-2 border-b pb-2">
        <Button variant={tab === 'assessments' ? 'default' : 'ghost'} onClick={() => setTab('assessments')}>
          Assessments ({assessments.length})
        </Button>
        <Button variant={tab === 'rules' ? 'default' : 'ghost'} onClick={() => setTab('rules')}>
          Rules ({rules.length})
        </Button>
      </div>

      {/* Override Modal */}
      {showOverride && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <Card className="w-full max-w-lg">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>Override Risk Level</CardTitle>
              <Button variant="ghost" size="icon" onClick={() => setShowOverride(null)}><X size={18} /></Button>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="bg-slate-50 rounded-lg p-3">
                <p className="text-sm"><strong>Current Score:</strong> {showOverride.total_score.toFixed(0)}</p>
                <p className="text-sm"><strong>Current Level:</strong> {showOverride.risk_level}</p>
              </div>
              <div>
                <label className="text-sm font-medium">New Risk Level</label>
                <Select value={overrideForm.level} onChange={e => setOverrideForm({ ...overrideForm, level: e.target.value })}>
                  <option value="">Select...</option>
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                  <option value="critical">Critical</option>
                </Select>
              </div>
              <div>
                <label className="text-sm font-medium">{t('case.reasoning')}</label>
                <Textarea value={overrideForm.reasoning} onChange={e => setOverrideForm({ ...overrideForm, reasoning: e.target.value })} placeholder="Structured reasoning for override..." rows={3} />
              </div>
              <div>
                <label className="text-sm font-medium">{t('case.confidence')} ({(overrideForm.confidence * 100).toFixed(0)}%)</label>
                <input type="range" min="0" max="1" step="0.05" value={overrideForm.confidence} onChange={e => setOverrideForm({ ...overrideForm, confidence: parseFloat(e.target.value) })} className="w-full" />
              </div>
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => setShowOverride(null)}>{t('common.cancel')}</Button>
                <Button className="bg-blue-600 hover:bg-blue-700" onClick={overrideRisk} disabled={!overrideForm.level || !overrideForm.reasoning}>
                  Apply Override
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Assessments Tab */}
      {tab === 'assessments' && (
        loading ? <p className="text-slate-500">{t('common.loading')}</p> :
        assessments.length === 0 ? (
          <Card><CardContent className="p-8 text-center text-slate-500">{t('common.no_data')}</CardContent></Card>
        ) : (
          <div className="grid gap-4">
            {assessments.map(a => (
              <Card key={a.id}>
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className={`w-16 h-16 rounded-xl bg-gradient-to-br ${getRiskGradient(a.total_score)} flex items-center justify-center text-white font-bold text-lg`}>
                        {a.total_score.toFixed(0)}
                      </div>
                      <div>
                        <p className="font-medium">Entity Assessment</p>
                        <p className="text-sm text-slate-500">{new Date(a.created_at).toLocaleString()}</p>
                        <div className="flex items-center gap-2 mt-1">
                          <Badge variant={(riskColors[a.override_level || a.risk_level] || 'secondary') as "success" | "warning" | "danger" | "destructive"}>
                            {(a.override_level || a.risk_level).toUpperCase()}
                          </Badge>
                          {a.override_level && <Badge variant="info">Overridden</Badge>}
                        </div>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <Button size="sm" variant="outline" onClick={() => { setShowOverride(a); setOverrideForm({ level: '', reasoning: '', confidence: 0.8 }); }}>
                        Override
                      </Button>
                    </div>
                  </div>
                  {a.factor_scores && Object.keys(a.factor_scores).length > 0 && (
                    <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-2">
                      {Object.entries(a.factor_scores).map(([factor, score]) => (
                        <div key={factor} className="bg-slate-50 rounded-lg p-2 text-center">
                          <p className="text-xs text-slate-500 capitalize">{factor}</p>
                          <p className="font-semibold">{(score as number).toFixed(0)}</p>
                        </div>
                      ))}
                    </div>
                  )}
                  {a.override_reasoning && (
                    <div className="mt-3 bg-amber-50 border border-amber-200 rounded-lg p-3">
                      <p className="text-sm text-amber-800"><strong>Override Reason:</strong> {a.override_reasoning}</p>
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        )
      )}

      {/* Rules Tab */}
      {tab === 'rules' && (
        <>
          <div className="flex justify-end">
            <Button size="sm" onClick={() => setShowRuleForm(true)} className="bg-blue-600 hover:bg-blue-700">
              <Plus size={14} className="me-1" /> Add Rule
            </Button>
          </div>
          {showRuleForm && (
            <Card>
              <CardContent className="p-4">
                <form onSubmit={createRule} className="space-y-3">
                  <div className="grid grid-cols-3 gap-3">
                    <div>
                      <label className="text-sm font-medium">Name</label>
                      <Input value={ruleForm.name} onChange={e => setRuleForm({ ...ruleForm, name: e.target.value })} required />
                    </div>
                    <div>
                      <label className="text-sm font-medium">Category</label>
                      <Select value={ruleForm.category} onChange={e => setRuleForm({ ...ruleForm, category: e.target.value })}>
                        <option value="country">Country</option>
                        <option value="industry">Industry</option>
                        <option value="ownership">Ownership</option>
                        <option value="transaction">Transaction</option>
                        <option value="pep">PEP</option>
                        <option value="sanctions">Sanctions</option>
                      </Select>
                    </div>
                    <div>
                      <label className="text-sm font-medium">Weight</label>
                      <Input type="number" step="0.1" min="0" max="5" value={ruleForm.weight} onChange={e => setRuleForm({ ...ruleForm, weight: parseFloat(e.target.value) })} />
                    </div>
                  </div>
                  <div>
                    <label className="text-sm font-medium">Description</label>
                    <Textarea value={ruleForm.description} onChange={e => setRuleForm({ ...ruleForm, description: e.target.value })} rows={2} />
                  </div>
                  <div className="flex justify-end gap-2">
                    <Button type="button" variant="outline" onClick={() => setShowRuleForm(false)}>{t('common.cancel')}</Button>
                    <Button type="submit" className="bg-blue-600 hover:bg-blue-700">{t('common.save')}</Button>
                  </div>
                </form>
              </CardContent>
            </Card>
          )}
          {rules.length === 0 ? (
            <Card><CardContent className="p-8 text-center text-slate-500">{t('common.no_data')}</CardContent></Card>
          ) : (
            <div className="bg-white rounded-xl border shadow overflow-hidden">
              <table className="w-full">
                <thead className="bg-slate-50 border-b">
                  <tr>
                    <th className="text-start p-3 text-sm font-medium text-slate-600">Rule Name</th>
                    <th className="text-start p-3 text-sm font-medium text-slate-600">Category</th>
                    <th className="text-start p-3 text-sm font-medium text-slate-600">Weight</th>
                    <th className="text-start p-3 text-sm font-medium text-slate-600">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {rules.map(rule => (
                    <tr key={rule.id} className="border-b hover:bg-slate-50">
                      <td className="p-3">
                        <p className="font-medium text-sm">{rule.name}</p>
                        <p className="text-xs text-slate-500">{rule.description}</p>
                      </td>
                      <td className="p-3 text-sm capitalize">{rule.category}</td>
                      <td className="p-3 text-sm font-medium">{rule.weight.toFixed(1)}x</td>
                      <td className="p-3">
                        <Badge variant={rule.is_active ? 'success' : 'secondary'}>
                          {rule.is_active ? 'Active' : 'Inactive'}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
