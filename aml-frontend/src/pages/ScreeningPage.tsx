import { useEffect, useState } from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Select } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import api from '@/services/api';
import { Shield, Search, CheckCircle, XCircle, HelpCircle, Brain, X, Database, Globe, RefreshCw } from 'lucide-react';

interface ScreeningResult {
  id: string;
  entity_id: string;
  screening_type: string;
  matched_name: string;
  match_score: number;
  match_source: string;
  match_details: Record<string, unknown> | null;
  status: string;
  resolution_reasoning: string | null;
  ai_suggestion: string | null;
  ai_confidence: number | null;
  ai_reasoning: string | null;
  created_at: string;
}

interface Entity {
  id: string;
  name: string;
  entity_type: string;
}

interface DataSourceInfo {
  sanctions: {
    primary: {
      source: string;
      individuals_count?: number;
      entities_count?: number;
      total_count?: number;
      last_updated?: string;
    };
    description: string;
    description_ar: string;
  };
  pep: {
    source: string;
    description: string;
    description_ar: string;
    count: number;
  };
}

export default function ScreeningPage() {
  const { t, language } = useLanguage();
  const [results, setResults] = useState<ScreeningResult[]>([]);
  const [entities, setEntities] = useState<Entity[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedResult, setSelectedResult] = useState<ScreeningResult | null>(null);
  const [resolveForm, setResolveForm] = useState({ status: '', reasoning: '', confidence: 0.8 });
  const [screenEntityId, setScreenEntityId] = useState('');
  const [screening, setScreening] = useState(false);
  const [dataSources, setDataSources] = useState<DataSourceInfo | null>(null);

  const loadData = () => {
    setLoading(true);
    Promise.all([
      api.get('/api/screening/results').catch(() => ({ data: [] })),
      api.get('/api/onboarding/entities').catch(() => ({ data: [] })),
      api.get('/api/screening/data-sources').catch(() => ({ data: null })),
    ]).then(([resultsRes, entitiesRes, sourcesRes]) => {
      setResults(Array.isArray(resultsRes.data) ? resultsRes.data : []);
      setEntities(Array.isArray(entitiesRes.data) ? entitiesRes.data : []);
      if (sourcesRes.data) setDataSources(sourcesRes.data);
    }).finally(() => setLoading(false));
  };

  useEffect(() => { loadData(); }, []);

  const screenEntity = async () => {
    if (!screenEntityId) return;
    setScreening(true);
    try {
      await api.post(`/api/screening/screen/${screenEntityId}`);
      loadData();
    } catch (err) {
      console.error('Screening failed', err);
    } finally {
      setScreening(false);
    }
  };

  const resolveMatch = async () => {
    if (!selectedResult) return;
    try {
      await api.post(`/api/screening/results/${selectedResult.id}/resolve`, {
        status: resolveForm.status,
        reasoning: resolveForm.reasoning,
        confidence_level: resolveForm.confidence,
      });
      setSelectedResult(null);
      setResolveForm({ status: '', reasoning: '', confidence: 0.8 });
      loadData();
    } catch (err) {
      console.error('Resolution failed', err);
    }
  };

  const statusIcons: Record<string, typeof CheckCircle> = {
    true_match: XCircle, false_positive: CheckCircle, inconclusive: HelpCircle,
  };

  const statusColors: Record<string, string> = {
    pending: 'warning', true_match: 'danger', false_positive: 'success', inconclusive: 'info',
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{t('screening.title')}</h1>
          <p className="text-slate-500 text-sm">{t('screening.subtitle')}</p>
        </div>
      </div>

      {/* Data Source Indicators */}
      {dataSources && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Card className="border-blue-200 bg-blue-50/50">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-blue-100 rounded-lg">
                  <Globe size={20} className="text-blue-700" />
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <h3 className="font-semibold text-sm text-blue-900">{t('screening.un_source')}</h3>
                    <Badge variant="info">LIVE</Badge>
                  </div>
                  <p className="text-xs text-blue-700 mt-0.5">
                    {language === 'ar' ? dataSources.sanctions.description_ar : dataSources.sanctions.description}
                  </p>
                  {dataSources.sanctions.primary.total_count && (
                    <p className="text-xs text-blue-600 mt-1">
                      {t('screening.total_entries')}: {dataSources.sanctions.primary.total_count.toLocaleString()}
                      {' '}({dataSources.sanctions.primary.individuals_count?.toLocaleString()} {t('screening.individuals')}, {dataSources.sanctions.primary.entities_count?.toLocaleString()} {t('screening.entities_label')})
                    </p>
                  )}
                  {dataSources.sanctions.primary.last_updated && (
                    <p className="text-xs text-blue-500 mt-0.5">
                      {t('screening.last_updated')}: {new Date(dataSources.sanctions.primary.last_updated).toLocaleString()}
                    </p>
                  )}
                </div>
                <Button variant="ghost" size="icon" onClick={loadData} title={t('screening.refresh')}>
                  <RefreshCw size={16} className="text-blue-600" />
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card className="border-green-200 bg-green-50/50">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-green-100 rounded-lg">
                  <Database size={20} className="text-green-700" />
                </div>
                <div className="flex-1">
                  <h3 className="font-semibold text-sm text-green-900">{t('screening.pep_source')}</h3>
                  <p className="text-xs text-green-700 mt-0.5">
                    {language === 'ar' ? dataSources.pep.description_ar : dataSources.pep.description}
                  </p>
                  <p className="text-xs text-green-600 mt-1">
                    {t('screening.total_entries')}: {dataSources.pep.count}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Screen Entity */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Shield size={20} /> {t('screening.screen')}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-3">
            <Select value={screenEntityId} onChange={e => setScreenEntityId(e.target.value)} className="flex-1">
              <option value="">Select an entity to screen...</option>
              {entities.map(e => (
                <option key={e.id} value={e.id}>{e.name} ({e.entity_type})</option>
              ))}
            </Select>
            <Button onClick={screenEntity} disabled={!screenEntityId || screening} className="bg-blue-600 hover:bg-blue-700">
              <Search size={16} className="me-2" /> {screening ? 'Screening...' : t('screening.screen')}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Resolve Modal */}
      {selectedResult && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <Card className="w-full max-w-lg">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>Resolve Screening Match</CardTitle>
              <Button variant="ghost" size="icon" onClick={() => setSelectedResult(null)}><X size={18} /></Button>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="bg-slate-50 rounded-lg p-4 space-y-2">
                <p className="text-sm"><strong>Matched Name:</strong> {selectedResult.matched_name}</p>
                <p className="text-sm"><strong>Score:</strong> {(selectedResult.match_score * 100).toFixed(0)}%</p>
                <p className="text-sm"><strong>Source:</strong> {selectedResult.match_source}</p>
                <p className="text-sm"><strong>Type:</strong> {selectedResult.screening_type}</p>
              </div>

              {selectedResult.ai_suggestion && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 space-y-2">
                  <div className="flex items-center gap-2">
                    <Brain size={16} className="text-blue-600" />
                    <span className="font-medium text-sm text-blue-900">{t('case.ai_suggestion')}</span>
                    <Badge variant="info">{(selectedResult.ai_confidence! * 100).toFixed(0)}% confident</Badge>
                  </div>
                  <p className="text-sm text-blue-800">Suggestion: <strong>{selectedResult.ai_suggestion}</strong></p>
                  <p className="text-sm text-blue-700">{selectedResult.ai_reasoning}</p>
                  <div className="flex gap-2 pt-1">
                    <Button size="sm" variant="success" onClick={() => setResolveForm({ ...resolveForm, status: selectedResult.ai_suggestion!, reasoning: selectedResult.ai_reasoning || '' })}>
                      {t('case.accept_ai')}
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => setResolveForm({ ...resolveForm, status: '', reasoning: '' })}>
                      {t('case.reject_ai')}
                    </Button>
                  </div>
                </div>
              )}

              <div>
                <label className="text-sm font-medium">{t('case.decision')}</label>
                <Select value={resolveForm.status} onChange={e => setResolveForm({ ...resolveForm, status: e.target.value })}>
                  <option value="">Select decision...</option>
                  <option value="true_match">{t('screening.true_match')}</option>
                  <option value="false_positive">{t('screening.false_positive')}</option>
                  <option value="inconclusive">{t('screening.inconclusive')}</option>
                </Select>
              </div>
              <div>
                <label className="text-sm font-medium">{t('case.reasoning')}</label>
                <Textarea value={resolveForm.reasoning} onChange={e => setResolveForm({ ...resolveForm, reasoning: e.target.value })} placeholder="Provide structured reasoning for your decision..." rows={3} />
              </div>
              <div>
                <label className="text-sm font-medium">{t('case.confidence')} ({(resolveForm.confidence * 100).toFixed(0)}%)</label>
                <input type="range" min="0" max="1" step="0.05" value={resolveForm.confidence} onChange={e => setResolveForm({ ...resolveForm, confidence: parseFloat(e.target.value) })} className="w-full" />
              </div>
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => setSelectedResult(null)}>{t('common.cancel')}</Button>
                <Button className="bg-blue-600 hover:bg-blue-700" onClick={resolveMatch} disabled={!resolveForm.status || !resolveForm.reasoning}>
                  {t('screening.resolve')}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Results Table */}
      {loading ? (
        <p className="text-slate-500">{t('common.loading')}</p>
      ) : results.length === 0 ? (
        <Card><CardContent className="p-8 text-center text-slate-500">{t('common.no_data')}</CardContent></Card>
      ) : (
        <div className="bg-white rounded-xl border shadow overflow-hidden">
          <table className="w-full">
            <thead className="bg-slate-50 border-b">
              <tr>
                <th className="text-start p-3 text-sm font-medium text-slate-600">Matched Name</th>
                <th className="text-start p-3 text-sm font-medium text-slate-600">Type</th>
                <th className="text-start p-3 text-sm font-medium text-slate-600">{t('screening.match_score')}</th>
                <th className="text-start p-3 text-sm font-medium text-slate-600">Source</th>
                <th className="text-start p-3 text-sm font-medium text-slate-600">{t('entity.status')}</th>
                <th className="text-start p-3 text-sm font-medium text-slate-600">{t('common.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {results.map(result => {
                const StatusIcon = statusIcons[result.status];
                return (
                  <tr key={result.id} className="border-b hover:bg-slate-50 transition-colors">
                    <td className="p-3 font-medium text-sm">{result.matched_name}</td>
                    <td className="p-3 text-sm capitalize">{result.screening_type}</td>
                    <td className="p-3">
                      <div className="flex items-center gap-2">
                        <div className="w-16 bg-slate-100 rounded-full h-2">
                          <div className="h-full rounded-full bg-red-500" style={{ width: `${result.match_score * 100}%` }} />
                        </div>
                        <span className="text-sm">{(result.match_score * 100).toFixed(0)}%</span>
                      </div>
                    </td>
                    <td className="p-3 text-sm">{result.match_source}</td>
                    <td className="p-3">
                      <Badge variant={(statusColors[result.status] || 'secondary') as "success" | "warning" | "info" | "danger"}>
                        {StatusIcon && <StatusIcon size={12} className="me-1" />}
                        {result.status.replace('_', ' ')}
                      </Badge>
                    </td>
                    <td className="p-3">
                      {result.status === 'pending' ? (
                        <Button size="sm" variant="outline" onClick={() => setSelectedResult(result)}>
                          {t('screening.resolve')}
                        </Button>
                      ) : (
                        <span className="text-xs text-slate-500">{result.resolution_reasoning?.substring(0, 40)}...</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
