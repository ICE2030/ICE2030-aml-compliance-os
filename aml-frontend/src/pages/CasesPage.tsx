import { useEffect, useState } from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import api from '@/services/api';
import { Briefcase, Search, Brain, Clock, X, Plus, GitCompare, CheckCircle, XCircle, Edit3, AlertTriangle } from 'lucide-react';

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

interface SimilarCase {
  case_id: string;
  case_number: string;
  title: string;
  case_type: string;
  decision: string | null;
  reasoning: string | null;
  entity_name: string | null;
  risk_level: string | null;
  similarity_score: number;
  similarity_method: string;
  time_to_decision_minutes: number | null;
  user_confidence: number | null;
}

const priorityColors: Record<string, string> = {
  low: 'secondary', medium: 'warning', high: 'danger', critical: 'destructive',
};
const statusColors: Record<string, string> = {
  open: 'info', assigned: 'info', under_investigation: 'warning',
  pending_decision: 'warning', escalated: 'danger',
  closed_no_action: 'success', closed_sar_filed: 'destructive', closed_other: 'secondary',
};

const REASONING_CATEGORIES = [
  { key: 'risk_factors', labelEn: 'Risk Factors', labelAr: '\u0639\u0648\u0627\u0645\u0644 \u0627\u0644\u0645\u062e\u0627\u0637\u0631' },
  { key: 'screening_match', labelEn: 'Screening Match', labelAr: '\u062a\u0637\u0627\u0628\u0642 \u0627\u0644\u0641\u062d\u0635' },
  { key: 'regulatory_concern', labelEn: 'Regulatory Concern', labelAr: '\u0642\u0644\u0642 \u062a\u0646\u0638\u064a\u0645\u064a' },
  { key: 'insufficient_info', labelEn: 'Insufficient Info', labelAr: '\u0645\u0639\u0644\u0648\u0645\u0627\u062a \u063a\u064a\u0631 \u0643\u0627\u0641\u064a\u0629' },
  { key: 'transaction_pattern', labelEn: 'Transaction Pattern', labelAr: '\u0646\u0645\u0637 \u0627\u0644\u0645\u0639\u0627\u0645\u0644\u0627\u062a' },
  { key: 'pep_exposure', labelEn: 'PEP Exposure', labelAr: '\u062a\u0639\u0631\u0636 \u0644\u0634\u062e\u0635 \u0633\u064a\u0627\u0633\u064a' },
  { key: 'geographic_risk', labelEn: 'Geographic Risk', labelAr: '\u0645\u062e\u0627\u0637\u0631 \u062c\u063a\u0631\u0627\u0641\u064a\u0629' },
];

export default function CasesPage() {
  const { t, language } = useLanguage();
  const [cases, setCases] = useState<Case[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [selectedCase, setSelectedCase] = useState<Case | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [entities, setEntities] = useState<Array<{ id: string; name: string }>>([]);
  const [createForm, setCreateForm] = useState({
    entity_id: '', case_type: 'manual_referral', priority: 'medium', title: '', description: '',
  });
  const [decisionForm, setDecisionForm] = useState({
    decision: '', reasoning_text: '', user_confidence: 0.8,
    reasoning_categories: {} as Record<string, boolean>,
    ai_disposition: '' as string,
  });
  const [similarCases, setSimilarCases] = useState<SimilarCase[]>([]);
  const [loadingSimilar, setLoadingSimilar] = useState(false);

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

  const loadSimilarCases = async (caseId: string) => {
    setLoadingSimilar(true);
    try {
      const res = await api.get(`/api/intelligence/cases/${caseId}/similar?limit=5`);
      setSimilarCases(Array.isArray(res.data) ? res.data : []);
    } catch {
      setSimilarCases([]);
    } finally {
      setLoadingSimilar(false);
    }
  };

  const openCase = (c: Case) => {
    setSelectedCase(c);
    setDecisionForm({ decision: '', reasoning_text: '', user_confidence: 0.8, reasoning_categories: {}, ai_disposition: '' });
    setSimilarCases([]);
    loadSimilarCases(c.id);
  };

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
      await api.post(`/api/intelligence/cases/${selectedCase.id}/decide`, {
        decision: decisionForm.decision,
        reasoning_text: decisionForm.reasoning_text,
        user_confidence: decisionForm.user_confidence,
        reasoning_categories: decisionForm.reasoning_categories,
        ai_disposition: decisionForm.ai_disposition || undefined,
      });
      setSelectedCase(null);
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

  const handleAcceptAi = () => {
    if (!selectedCase) return;
    setDecisionForm({ ...decisionForm, decision: 'no_action', reasoning_text: selectedCase.ai_suggestion || '', ai_disposition: 'accepted' });
  };
  const handleRejectAi = () => {
    setDecisionForm({ ...decisionForm, decision: '', reasoning_text: '', ai_disposition: 'rejected' });
  };
  const handleEditAi = () => {
    if (!selectedCase) return;
    setDecisionForm({ ...decisionForm, reasoning_text: selectedCase.ai_suggestion || '', ai_disposition: 'edited' });
  };

  const toggleCategory = (key: string) => {
    setDecisionForm({
      ...decisionForm,
      reasoning_categories: { ...decisionForm.reasoning_categories, [key]: !decisionForm.reasoning_categories[key] },
    });
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
          <p className="text-slate-500 text-sm">{t('case.subtitle')}</p>
        </div>
        <Button onClick={() => setShowCreate(true)} className="bg-blue-600 hover:bg-blue-700">
          <Plus size={16} className="me-2" /> {t('case.create')}
        </Button>
      </div>

      <div className="flex gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
          <Input placeholder={t('common.search')} value={search} onChange={e => setSearch(e.target.value)} className="ps-9" />
        </div>
        <Select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} className="w-48">
          <option value="">{t('case.all_statuses')}</option>
          <option value="open">{t('case.status_open')}</option>
          <option value="assigned">{t('case.status_assigned')}</option>
          <option value="under_investigation">{t('case.status_investigating')}</option>
          <option value="pending_decision">{t('case.status_pending')}</option>
          <option value="escalated">{t('case.status_escalated')}</option>
          <option value="closed_no_action">{t('case.status_closed_no_action')}</option>
          <option value="closed_sar_filed">{t('case.status_closed_sar')}</option>
        </Select>
      </div>

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

      {selectedCase && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <Card className="w-full max-w-4xl max-h-[90vh] overflow-auto">
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2"><Briefcase size={20} /> {selectedCase.case_number}</CardTitle>
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
                <div className="bg-slate-50 rounded-lg p-3"><p className="text-sm">{selectedCase.description}</p></div>
              )}

              {/* Similar Cases Panel - Phase 3 */}
              <div className="border rounded-lg p-4 space-y-3">
                <h4 className="font-medium flex items-center gap-2">
                  <GitCompare size={16} className="text-purple-600" /> {t('case.similar_cases')}
                </h4>
                {loadingSimilar ? (
                  <p className="text-sm text-slate-400">{t('common.loading')}</p>
                ) : similarCases.length === 0 ? (
                  <p className="text-sm text-slate-400">{t('case.no_similar')}</p>
                ) : (
                  <div className="space-y-2">
                    <p className="text-xs text-slate-500">{t('case.similar_count').replace('{count}', String(similarCases.length))}</p>
                    {similarCases.map(sc => (
                      <div key={sc.case_id} className="bg-purple-50 rounded-lg p-3 border border-purple-100">
                        <div className="flex items-center justify-between">
                          <div>
                            <span className="font-mono text-sm text-purple-700">{sc.case_number}</span>
                            <span className="text-sm ms-2">{sc.title}</span>
                          </div>
                          <Badge variant="secondary">{(sc.similarity_score * 100).toFixed(0)}% {t('case.match')}</Badge>
                        </div>
                        <div className="flex gap-4 mt-1 text-xs text-slate-600">
                          {sc.decision && <span>{t('case.decision')}: <strong className="capitalize">{sc.decision.replace('_', ' ')}</strong></span>}
                          {sc.entity_name && <span>{t('case.entity')}: {sc.entity_name}</span>}
                          {sc.risk_level && <span>{t('risk.level')}: <span className="capitalize">{sc.risk_level}</span></span>}
                          {sc.user_confidence != null && <span>{t('case.confidence')}: {(sc.user_confidence * 100).toFixed(0)}%</span>}
                        </div>
                        {sc.reasoning && <p className="text-xs text-slate-500 mt-1 line-clamp-2">{sc.reasoning}</p>}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* AI Suggestion Panel */}
              <div className="border rounded-lg p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="font-medium flex items-center gap-2"><Brain size={16} className="text-blue-600" /> {t('case.ai_assistant')}</h4>
                  <Button size="sm" variant="outline" onClick={() => getAiSuggestion(selectedCase.id)}>{t('case.get_ai')}</Button>
                </div>
                {selectedCase.ai_summary && (
                  <div className="bg-blue-50 rounded-lg p-3 space-y-2">
                    <p className="text-sm text-blue-900"><strong>{t('case.ai_summary')}:</strong> {selectedCase.ai_summary}</p>
                    {selectedCase.ai_suggestion && (
                      <>
                        <p className="text-sm text-blue-800"><strong>{t('case.ai_suggestion')}:</strong> {selectedCase.ai_suggestion}</p>
                        <div className="flex gap-2 pt-1">
                          <Button size="sm" variant="success" onClick={handleAcceptAi}><CheckCircle size={14} className="me-1" /> {t('case.accept_ai')}</Button>
                          <Button size="sm" variant="outline" onClick={handleRejectAi}><XCircle size={14} className="me-1" /> {t('case.reject_ai')}</Button>
                          <Button size="sm" variant="secondary" onClick={handleEditAi}><Edit3 size={14} className="me-1" /> {t('case.edit_ai')}</Button>
                        </div>
                        {decisionForm.ai_disposition && (
                          <p className="text-xs text-blue-700 mt-1">{t('case.ai_disposition')}: <strong className="capitalize">{decisionForm.ai_disposition}</strong></p>
                        )}
                      </>
                    )}
                  </div>
                )}
              </div>

              {/* Decision Form - Phase 3 Enhanced */}
              {!selectedCase.decision && (
                <div className="border-t pt-4 space-y-4">
                  <h4 className="font-medium flex items-center gap-2"><AlertTriangle size={16} className="text-amber-600" /> {t('case.decide')}</h4>
                  <div>
                    <label className="text-sm font-medium">{t('case.decision')}</label>
                    <Select value={decisionForm.decision} onChange={e => setDecisionForm({ ...decisionForm, decision: e.target.value })}>
                      <option value="">{t('case.select_decision')}</option>
                      <option value="no_action">{t('case.decision_no_action')}</option>
                      <option value="approve">{t('case.decision_approve')}</option>
                      <option value="sar_filed">{t('case.decision_sar')}</option>
                      <option value="escalate">{t('case.decision_escalate')}</option>
                      <option value="reject">{t('case.decision_reject')}</option>
                    </Select>
                  </div>
                  <div>
                    <label className="text-sm font-medium mb-2 block">{t('case.reasoning_categories')}</label>
                    <div className="flex flex-wrap gap-2">
                      {REASONING_CATEGORIES.map(cat => (
                        <button key={cat.key} type="button" onClick={() => toggleCategory(cat.key)}
                          className={`px-3 py-1 text-xs rounded-full border transition-colors ${
                            decisionForm.reasoning_categories[cat.key]
                              ? 'bg-blue-100 border-blue-300 text-blue-800'
                              : 'bg-white border-slate-200 text-slate-600 hover:border-blue-200'
                          }`}>
                          {language === 'ar' ? cat.labelAr : cat.labelEn}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <label className="text-sm font-medium">{t('case.reasoning')}</label>
                    <Textarea value={decisionForm.reasoning_text} onChange={e => setDecisionForm({ ...decisionForm, reasoning_text: e.target.value })} placeholder={t('case.reasoning_placeholder')} rows={3} />
                  </div>
                  <div>
                    <label className="text-sm font-medium">{t('case.confidence')} - {(decisionForm.user_confidence * 100).toFixed(0)}%</label>
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-slate-400">{t('common.low')}</span>
                      <input type="range" min="0" max="1" step="0.05" value={decisionForm.user_confidence} onChange={e => setDecisionForm({ ...decisionForm, user_confidence: parseFloat(e.target.value) })} className="flex-1" />
                      <span className="text-xs text-slate-400">{t('common.high')}</span>
                    </div>
                  </div>
                  <Button className="bg-blue-600 hover:bg-blue-700 w-full" onClick={makeDecision} disabled={!decisionForm.decision || !decisionForm.reasoning_text}>
                    {t('common.confirm')} {t('case.decision')}
                  </Button>
                </div>
              )}

              {selectedCase.decision && (
                <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                  <h4 className="font-medium text-green-900">{t('case.decision_made')}</h4>
                  <p className="text-sm text-green-800 mt-1"><strong>{t('case.decision')}:</strong> {selectedCase.decision.replace('_', ' ')}</p>
                  <p className="text-sm text-green-800"><strong>{t('case.reasoning')}:</strong> {selectedCase.decision_reasoning}</p>
                  {selectedCase.time_to_decision_minutes != null && (
                    <p className="text-xs text-green-600 mt-1 flex items-center gap-1">
                      <Clock size={12} /> {t('case.resolved_in').replace('{minutes}', String(selectedCase.time_to_decision_minutes))}
                    </p>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

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
                    <Button size="sm" variant="outline" onClick={() => openCase(c)}>
                      {c.decision ? t('common.view') : t('case.investigate')}
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
