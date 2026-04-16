import { useEffect, useState } from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import api from '@/services/api';
import { Briefcase, Search, Brain, Clock, X, Plus } from 'lucide-react';

interface Case {
  id: string;
  case_number: string;
  entity_id: string;
  case_type: string;
  priority: string;
  status: string;
  title: string;
  description: string | null;
  assigned_to: string | null;
  sla_deadline: string | null;
  sla_breached: boolean;
  decision: string | null;
  decision_reasoning: string | null;
  ai_summary: string | null;
  ai_suggestion: string | null;
  ai_suggestion_accepted: boolean | null;
  time_to_decision_minutes: number | null;
  created_at: string;
}

const priorityColors: Record<string, string> = {
  low: 'secondary', medium: 'warning', high: 'danger', critical: 'destructive',
};
const statusColors: Record<string, string> = {
  open: 'info', assigned: 'info', under_investigation: 'warning',
  pending_decision: 'warning', escalated: 'danger',
  closed_no_action: 'success', closed_sar_filed: 'destructive', closed_other: 'secondary',
};

export default function CasesPage() {
  const { t } = useLanguage();
  const [cases, setCases] = useState<Case[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [selectedCase, setSelectedCase] = useState<Case | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [decisionForm, setDecisionForm] = useState({ decision: '', reasoning: '', confidence: 0.8 });
  const [entities, setEntities] = useState<Array<{ id: string; name: string }>>([]);
  const [createForm, setCreateForm] = useState({
    entity_id: '', case_type: 'manual_referral', priority: 'medium', title: '', description: '',
  });

  const loadData = () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (statusFilter) params.set('status', statusFilter);
    Promise.all([
      api.get(`/api/cases/?${params}`).catch(() => ({ data: [] })),
      api.get('/api/onboarding/entities').catch(() => ({ data: [] })),
    ]).then(([casesRes, entitiesRes]) => {
      setCases(Array.isArray(casesRes.data) ? casesRes.data : []);
      setEntities(Array.isArray(entitiesRes.data) ? entitiesRes.data : []);
    }).finally(() => setLoading(false));
  };

  useEffect(() => { loadData(); }, [statusFilter]);

  const createCase = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.post('/api/cases/', createForm);
      setShowCreate(false);
      setCreateForm({ entity_id: '', case_type: 'manual_referral', priority: 'medium', title: '', description: '' });
      loadData();
    } catch (err) { console.error(err); }
  };

  const makeDecision = async () => {
    if (!selectedCase) return;
    try {
      await api.post(`/api/cases/${selectedCase.id}/decide`, {
        decision: decisionForm.decision,
        reasoning: decisionForm.reasoning,
        confidence_level: decisionForm.confidence,
      });
      setSelectedCase(null);
      setDecisionForm({ decision: '', reasoning: '', confidence: 0.8 });
      loadData();
    } catch (err) { console.error(err); }
  };

  const getAiSuggestion = async (caseId: string) => {
    try {
      const res = await api.post(`/api/cases/${caseId}/ai-suggest`);
      if (selectedCase && selectedCase.id === caseId) {
        setSelectedCase({ ...selectedCase, ai_suggestion: res.data.suggestion, ai_summary: res.data.summary });
      }
    } catch (err) { console.error(err); }
  };

  const filtered = cases.filter(c =>
    c.case_number.toLowerCase().includes(search.toLowerCase()) ||
    c.title.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{t('case.title')}</h1>
          <p className="text-slate-500 text-sm">Investigation & Decision Management</p>
        </div>
        <Button onClick={() => setShowCreate(true)} className="bg-blue-600 hover:bg-blue-700">
          <Plus size={16} className="me-2" /> {t('case.create')}
        </Button>
      </div>

      {/* Filters */}
      <div className="flex gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
          <Input placeholder={t('common.search')} value={search} onChange={e => setSearch(e.target.value)} className="ps-9" />
        </div>
        <Select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} className="w-48">
          <option value="">All Statuses</option>
          <option value="open">Open</option>
          <option value="assigned">Assigned</option>
          <option value="under_investigation">Under Investigation</option>
          <option value="pending_decision">Pending Decision</option>
          <option value="escalated">Escalated</option>
          <option value="closed_no_action">Closed - No Action</option>
          <option value="closed_sar_filed">Closed - SAR Filed</option>
        </Select>
      </div>

      {/* Create Modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <Card className="w-full max-w-lg">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>{t('case.create')}</CardTitle>
              <Button variant="ghost" size="icon" onClick={() => setShowCreate(false)}><X size={18} /></Button>
            </CardHeader>
            <CardContent>
              <form onSubmit={createCase} className="space-y-4">
                <div>
                  <label className="text-sm font-medium">Entity</label>
                  <Select value={createForm.entity_id} onChange={e => setCreateForm({ ...createForm, entity_id: e.target.value })} required>
                    <option value="">Select entity...</option>
                    {entities.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
                  </Select>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm font-medium">Type</label>
                    <Select value={createForm.case_type} onChange={e => setCreateForm({ ...createForm, case_type: e.target.value })}>
                      <option value="manual_referral">Manual Referral</option>
                      <option value="screening_match">Screening Match</option>
                      <option value="transaction_alert">Transaction Alert</option>
                      <option value="periodic_review">Periodic Review</option>
                      <option value="risk_escalation">Risk Escalation</option>
                    </Select>
                  </div>
                  <div>
                    <label className="text-sm font-medium">{t('case.priority')}</label>
                    <Select value={createForm.priority} onChange={e => setCreateForm({ ...createForm, priority: e.target.value })}>
                      <option value="low">{t('common.low')}</option>
                      <option value="medium">{t('common.medium')}</option>
                      <option value="high">{t('common.high')}</option>
                      <option value="critical">{t('common.critical')}</option>
                    </Select>
                  </div>
                </div>
                <div>
                  <label className="text-sm font-medium">Title</label>
                  <Input value={createForm.title} onChange={e => setCreateForm({ ...createForm, title: e.target.value })} required />
                </div>
                <div>
                  <label className="text-sm font-medium">Description</label>
                  <Textarea value={createForm.description} onChange={e => setCreateForm({ ...createForm, description: e.target.value })} rows={3} />
                </div>
                <div className="flex justify-end gap-2">
                  <Button type="button" variant="outline" onClick={() => setShowCreate(false)}>{t('common.cancel')}</Button>
                  <Button type="submit" className="bg-blue-600 hover:bg-blue-700">{t('common.save')}</Button>
                </div>
              </form>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Case Detail / Decision */}
      {selectedCase && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <Card className="w-full max-w-2xl max-h-[90vh] overflow-auto">
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Briefcase size={20} /> {selectedCase.case_number}
                </CardTitle>
                <p className="text-sm text-slate-500 mt-1">{selectedCase.title}</p>
              </div>
              <Button variant="ghost" size="icon" onClick={() => setSelectedCase(null)}><X size={18} /></Button>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div><span className="text-slate-500">Type:</span> <span className="font-medium capitalize">{selectedCase.case_type.replace('_', ' ')}</span></div>
                <div><span className="text-slate-500">Priority:</span> <Badge variant={(priorityColors[selectedCase.priority] || 'secondary') as "warning" | "danger" | "destructive" | "secondary"}>{selectedCase.priority}</Badge></div>
                <div><span className="text-slate-500">Status:</span> <Badge variant={(statusColors[selectedCase.status] || 'secondary') as "info" | "warning" | "danger" | "success" | "destructive" | "secondary"}>{selectedCase.status.replace('_', ' ')}</Badge></div>
                <div><span className="text-slate-500">SLA:</span> {selectedCase.sla_deadline ? new Date(selectedCase.sla_deadline).toLocaleDateString() : 'N/A'} {selectedCase.sla_breached && <Badge variant="destructive">BREACHED</Badge>}</div>
              </div>

              {selectedCase.description && (
                <div className="bg-slate-50 rounded-lg p-3">
                  <p className="text-sm">{selectedCase.description}</p>
                </div>
              )}

              {/* AI Suggestion Panel */}
              <div className="border rounded-lg p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="font-medium flex items-center gap-2"><Brain size={16} className="text-blue-600" /> AI Assistant</h4>
                  <Button size="sm" variant="outline" onClick={() => getAiSuggestion(selectedCase.id)}>Get AI Suggestion</Button>
                </div>
                {selectedCase.ai_summary && (
                  <div className="bg-blue-50 rounded-lg p-3 space-y-2">
                    <p className="text-sm text-blue-900"><strong>Summary:</strong> {selectedCase.ai_summary}</p>
                    {selectedCase.ai_suggestion && (
                      <>
                        <p className="text-sm text-blue-800"><strong>Suggestion:</strong> {selectedCase.ai_suggestion}</p>
                        <div className="flex gap-2 pt-1">
                          <Button size="sm" variant="success" onClick={() => setDecisionForm({ ...decisionForm, decision: 'close_no_action', reasoning: selectedCase.ai_suggestion || '' })}>
                            {t('case.accept_ai')}
                          </Button>
                          <Button size="sm" variant="outline" onClick={() => setDecisionForm({ ...decisionForm, decision: '', reasoning: '' })}>
                            {t('case.reject_ai')}
                          </Button>
                          <Button size="sm" variant="secondary" onClick={() => setDecisionForm({ ...decisionForm, reasoning: selectedCase.ai_suggestion || '' })}>
                            {t('case.edit_ai')}
                          </Button>
                        </div>
                      </>
                    )}
                  </div>
                )}
              </div>

              {/* Decision Form */}
              {!selectedCase.decision && (
                <div className="border-t pt-4 space-y-3">
                  <h4 className="font-medium">{t('case.decide')}</h4>
                  <div>
                    <label className="text-sm font-medium">{t('case.decision')}</label>
                    <Select value={decisionForm.decision} onChange={e => setDecisionForm({ ...decisionForm, decision: e.target.value })}>
                      <option value="">Select decision...</option>
                      <option value="close_no_action">Close - No Action Required</option>
                      <option value="close_sar_filed">Close - SAR Filed</option>
                      <option value="escalate">Escalate</option>
                      <option value="close_other">Close - Other</option>
                    </Select>
                  </div>
                  <div>
                    <label className="text-sm font-medium">{t('case.reasoning')}</label>
                    <Textarea value={decisionForm.reasoning} onChange={e => setDecisionForm({ ...decisionForm, reasoning: e.target.value })} placeholder="Provide structured reasoning for your decision..." rows={3} />
                  </div>
                  <div>
                    <label className="text-sm font-medium">{t('case.confidence')} ({(decisionForm.confidence * 100).toFixed(0)}%)</label>
                    <input type="range" min="0" max="1" step="0.05" value={decisionForm.confidence} onChange={e => setDecisionForm({ ...decisionForm, confidence: parseFloat(e.target.value) })} className="w-full" />
                  </div>
                  <Button className="bg-blue-600 hover:bg-blue-700" onClick={makeDecision} disabled={!decisionForm.decision || !decisionForm.reasoning}>
                    {t('common.confirm')} {t('case.decision')}
                  </Button>
                </div>
              )}

              {selectedCase.decision && (
                <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                  <h4 className="font-medium text-green-900">Decision Made</h4>
                  <p className="text-sm text-green-800 mt-1"><strong>Decision:</strong> {selectedCase.decision.replace('_', ' ')}</p>
                  <p className="text-sm text-green-800"><strong>Reasoning:</strong> {selectedCase.decision_reasoning}</p>
                  {selectedCase.time_to_decision_minutes && (
                    <p className="text-xs text-green-600 mt-1 flex items-center gap-1">
                      <Clock size={12} /> Resolved in {selectedCase.time_to_decision_minutes} minutes
                    </p>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* Cases Table */}
      {loading ? (
        <p className="text-slate-500">{t('common.loading')}</p>
      ) : filtered.length === 0 ? (
        <Card><CardContent className="p-8 text-center text-slate-500">{t('common.no_data')}</CardContent></Card>
      ) : (
        <div className="bg-white rounded-xl border shadow overflow-hidden">
          <table className="w-full">
            <thead className="bg-slate-50 border-b">
              <tr>
                <th className="text-start p-3 text-sm font-medium text-slate-600">Case #</th>
                <th className="text-start p-3 text-sm font-medium text-slate-600">Title</th>
                <th className="text-start p-3 text-sm font-medium text-slate-600">Type</th>
                <th className="text-start p-3 text-sm font-medium text-slate-600">{t('case.priority')}</th>
                <th className="text-start p-3 text-sm font-medium text-slate-600">{t('case.status')}</th>
                <th className="text-start p-3 text-sm font-medium text-slate-600">SLA</th>
                <th className="text-start p-3 text-sm font-medium text-slate-600">{t('common.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(c => (
                <tr key={c.id} className="border-b hover:bg-slate-50 transition-colors">
                  <td className="p-3 font-mono text-sm">{c.case_number}</td>
                  <td className="p-3 text-sm font-medium">{c.title}</td>
                  <td className="p-3 text-sm capitalize">{c.case_type.replace('_', ' ')}</td>
                  <td className="p-3"><Badge variant={(priorityColors[c.priority] || 'secondary') as "warning" | "danger" | "destructive" | "secondary"}>{c.priority}</Badge></td>
                  <td className="p-3"><Badge variant={(statusColors[c.status] || 'secondary') as "info" | "warning" | "danger" | "success" | "destructive" | "secondary"}>{c.status.replace('_', ' ')}</Badge></td>
                  <td className="p-3 text-sm">
                    {c.sla_deadline ? new Date(c.sla_deadline).toLocaleDateString() : '-'}
                    {c.sla_breached && <Badge variant="destructive" className="ms-1">!</Badge>}
                  </td>
                  <td className="p-3">
                    <Button size="sm" variant="outline" onClick={() => { setSelectedCase(c); setDecisionForm({ decision: '', reasoning: '', confidence: 0.8 }); }}>
                      {c.decision ? 'View' : 'Investigate'}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
