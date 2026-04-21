import { useState, useEffect, useCallback } from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import api from '@/services/api';
import { Button } from '@/components/ui/button';
import { Lightbulb, Check, RefreshCw, ChevronDown, ChevronUp, Sparkles, Shield } from 'lucide-react';

interface SuggestedControl {
  name: string;
  name_ar: string;
  objective: string;
  objective_ar: string;
  control_type: string;
  suggested_owner: string;
  suggested_frequency: string;
  rationale: string;
  rationale_ar: string;
  confidence: number;
}

interface Suggestion {
  obligation_id: string;
  obligation_type: string;
  obligation_text: string;
  sub_type: string | null;
  is_suggestion: boolean;
  status: string;
  existing_controls_count: number;
  suggested_control: SuggestedControl;
  provenance: {
    provision_id: string;
    provision_section?: string;
    provision_title?: string;
    source_title?: string;
    regulator?: string;
  };
}

export default function ControlSuggestionsPage() {
  const { t, language } = useLanguage();
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [accepting, setAccepting] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [onlyUnmapped, setOnlyUnmapped] = useState(true);
  const [total, setTotal] = useState(0);

  const loadSuggestions = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/api/phase5a/suggestions', {
        params: { only_unmapped: onlyUnmapped },
      });
      setSuggestions(res.data.suggestions || []);
      setTotal(res.data.total_suggestions || 0);
    } catch { /* ignore */ }
    setLoading(false);
  }, [onlyUnmapped]);

  useEffect(() => { loadSuggestions(); }, [loadSuggestions]);

  const handleAccept = async (obligationId: string) => {
    setAccepting(obligationId);
    try {
      await api.post(`/api/phase5a/suggestions/${obligationId}/accept`);
      setSuggestions(prev => prev.filter(s => s.obligation_id !== obligationId));
      setTotal(prev => prev - 1);
    } catch { /* ignore */ }
    setAccepting(null);
  };

  const typeColors: Record<string, string> = {
    policy: 'bg-blue-100 text-blue-800', procedure: 'bg-purple-100 text-purple-800',
    technical: 'bg-green-100 text-green-800', monitoring: 'bg-amber-100 text-amber-800',
    training: 'bg-pink-100 text-pink-800',
  };

  const confidenceColor = (c: number) => {
    if (c >= 0.85) return 'text-green-600';
    if (c >= 0.70) return 'text-amber-600';
    return 'text-red-600';
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <Lightbulb className="text-amber-500" size={28} />
            {t('p5a.suggestions_title')}
          </h1>
          <p className="text-slate-500 mt-1">{t('p5a.suggestions_subtitle')}</p>
        </div>
        <Button onClick={loadSuggestions} variant="outline" className="gap-2">
          <RefreshCw size={16} /> {t('p4.refresh')}
        </Button>
      </div>

      {/* Filters */}
      <div className="flex gap-4 items-center">
        <label className="flex items-center gap-2 text-sm text-slate-600">
          <input
            type="checkbox"
            checked={onlyUnmapped}
            onChange={e => setOnlyUnmapped(e.target.checked)}
            className="rounded"
          />
          {t('p5a.only_unmapped')}
        </label>
        <span className="text-sm text-slate-400">{total} {t('p5a.suggestions_count')}</span>
      </div>

      {/* Info banner */}
      <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 flex items-start gap-3">
        <Sparkles className="text-amber-500 mt-0.5 shrink-0" size={20} />
        <div>
          <p className="text-sm font-medium text-amber-800">{t('p5a.ai_disclaimer_title')}</p>
          <p className="text-sm text-amber-700 mt-1">{t('p5a.ai_disclaimer')}</p>
        </div>
      </div>

      {/* Suggestions list */}
      {loading ? (
        <div className="text-center py-12 text-slate-400">{t('common.loading')}</div>
      ) : suggestions.length === 0 ? (
        <div className="text-center py-12 bg-white rounded-xl border">
          <Shield className="mx-auto text-slate-300" size={48} />
          <p className="text-slate-500 mt-3">{t('p5a.no_suggestions')}</p>
          <p className="text-sm text-slate-400 mt-1">{t('p5a.no_suggestions_hint')}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {suggestions.map(s => {
            const sc = s.suggested_control;
            const isExpanded = expandedId === s.obligation_id;

            return (
              <div key={s.obligation_id} className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                <div className="p-4">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      {/* Suggested control name */}
                      <div className="flex items-center gap-3 flex-wrap">
                        <h3 className="font-semibold text-slate-900">
                          {language === 'ar' ? sc.name_ar : sc.name}
                        </h3>
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${typeColors[sc.control_type] || 'bg-slate-100'}`}>
                          {t(`p4.type_${sc.control_type}`)}
                        </span>
                        <span className={`text-xs font-medium ${confidenceColor(sc.confidence)}`}>
                          {t('p5a.confidence')}: {Math.round(sc.confidence * 100)}%
                        </span>
                        {s.sub_type && (
                          <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-indigo-100 text-indigo-800">
                            {s.sub_type.replace(/_/g, ' ')}
                          </span>
                        )}
                      </div>

                      {/* Objective */}
                      <p className="text-sm text-slate-600 mt-1">
                        {language === 'ar' ? sc.objective_ar : sc.objective}
                      </p>

                      {/* Meta */}
                      <div className="flex gap-4 mt-2 text-xs text-slate-400 flex-wrap">
                        <span>{t('p4.owner')}: {sc.suggested_owner}</span>
                        <span>{t('p4.frequency')}: {sc.suggested_frequency}</span>
                        {s.provenance.regulator && <span>{t('regsearch.regulator')}: {s.provenance.regulator}</span>}
                        {s.existing_controls_count > 0 && (
                          <span className="text-amber-600">{s.existing_controls_count} {t('p5a.existing_controls')}</span>
                        )}
                      </div>
                    </div>

                    <div className="flex gap-1 shrink-0">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => setExpandedId(isExpanded ? null : s.obligation_id)}
                      >
                        {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                      </Button>
                      <Button
                        size="sm"
                        className="gap-1"
                        disabled={accepting === s.obligation_id}
                        onClick={() => handleAccept(s.obligation_id)}
                      >
                        <Check size={14} />
                        {accepting === s.obligation_id ? t('common.loading') : t('p5a.accept')}
                      </Button>
                    </div>
                  </div>
                </div>

                {/* Expanded: obligation details + rationale */}
                {isExpanded && (
                  <div className="border-t bg-slate-50 p-4 space-y-3">
                    <div>
                      <h4 className="text-sm font-medium text-slate-700">{t('p5a.source_obligation')}</h4>
                      <p className="text-sm text-slate-600 mt-1 bg-white p-3 rounded-lg border">{s.obligation_text}</p>
                      <div className="flex gap-3 mt-2 text-xs text-slate-400">
                        <span className="bg-slate-100 px-2 py-0.5 rounded">{s.obligation_type}</span>
                        {s.provenance.provision_title && (
                          <span>{t('regsearch.provision')}: {s.provenance.provision_title}</span>
                        )}
                        {s.provenance.source_title && (
                          <span>{t('regsearch.source')}: {s.provenance.source_title}</span>
                        )}
                      </div>
                    </div>
                    <div>
                      <h4 className="text-sm font-medium text-slate-700">{t('p5a.rationale')}</h4>
                      <p className="text-sm text-slate-600 mt-1">
                        {language === 'ar' ? sc.rationale_ar : sc.rationale}
                      </p>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
