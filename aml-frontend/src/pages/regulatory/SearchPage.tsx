import { useState } from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Search, ExternalLink, AlertTriangle, BookOpen, Scale, Info, ChevronDown, ChevronUp } from 'lucide-react';
import api from '@/services/api';

interface Citation {
  source_title: string;
  source_title_ar?: string;
  source_url?: string;
  regulator: string;
  regulator_ar?: string;
  regulator_abbreviation: string;
  jurisdiction: string;
  jurisdiction_code: string;
  authority_level: string;
  is_binding: boolean;
  binding_status: string;
  provision_id: string;
  provision_section?: string;
  provision_title?: string;
  provision_text?: string;
  provision_text_ar?: string;
  relevance_score: number;
  retrieval_method: string;
}

interface SearchResult {
  query: string;
  answer: string;
  answer_ar: string;
  confidence: number;
  total_results: number;
  topics_matched: string[];
  retrieval_methods_used: string[];
  citations: Citation[];
  gaps_detected: string[];
  disclaimer?: string;
  disclaimer_ar?: string;
}

const SAMPLE_QUERIES = [
  'Customer due diligence requirements',
  'Suspicious transaction reporting obligations',
  'Beneficial ownership transparency',
  'Targeted financial sanctions',
  'Wire transfer transparency requirements',
  'Risk-based approach for financial institutions',
];

export default function SearchPage() {
  const { t, language } = useLanguage();
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SearchResult | null>(null);
  const [error, setError] = useState('');
  const [regulatorFilter, setRegulatorFilter] = useState('');
  const [expandedCitations, setExpandedCitations] = useState<Set<number>>(new Set());

  const handleSearch = async (searchQuery?: string) => {
    const q = searchQuery || query;
    if (!q.trim()) return;

    setLoading(true);
    setError('');
    setResult(null);

    try {
      const response = await api.post('/api/regulatory/ask', {
        query: q,
        regulator_filter: regulatorFilter || undefined,
        limit: 10,
      });
      setResult(response.data);
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail || 'Search failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const toggleCitation = (index: number) => {
    setExpandedCitations(prev => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.7) return 'text-emerald-600';
    if (confidence >= 0.4) return 'text-amber-600';
    return 'text-red-500';
  };

  const getConfidenceBg = (confidence: number) => {
    if (confidence >= 0.7) return 'bg-emerald-50 border-emerald-200';
    if (confidence >= 0.4) return 'bg-amber-50 border-amber-200';
    return 'bg-red-50 border-red-200';
  };

  const getTierLabel = (tier: string) => {
    const labels: Record<string, string> = {
      tier_1: 'Tier 1 — Binding Law/Regulation',
      tier_2: 'Tier 2 — Official Guidance',
      tier_3: 'Tier 3 — Draft/Consultation',
      tier_4: 'Tier 4 — Secondary Commentary',
    };
    return labels[tier] || tier;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-800">{t('regsearch.title')}</h1>
        <p className="text-slate-500 mt-1">{t('regsearch.subtitle')}</p>
      </div>

      {/* Search Box */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex gap-3">
            <div className="flex-1">
              <Input
                placeholder={t('regsearch.placeholder')}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                className="text-base"
              />
            </div>
            <select
              value={regulatorFilter}
              onChange={(e) => setRegulatorFilter(e.target.value)}
              className="border border-slate-200 rounded-lg px-3 text-sm bg-white"
            >
              <option value="">{t('regsearch.all')}</option>
              <option value="FATF">FATF</option>
              <option value="SAMA">SAMA</option>
              <option value="AML-SA">Saudi AML</option>
              <option value="CMA">CMA</option>
              <option value="IA-SA">Insurance Authority</option>
            </select>
            <Button onClick={() => handleSearch()} disabled={loading || !query.trim()}>
              <Search size={18} className="me-2" />
              {loading ? '...' : t('regsearch.ask')}
            </Button>
          </div>

          {/* Sample queries */}
          <div className="mt-4">
            <p className="text-xs text-slate-400 mb-2">{t('regsearch.sample_queries')}:</p>
            <div className="flex flex-wrap gap-2">
              {SAMPLE_QUERIES.map((sq) => (
                <button
                  key={sq}
                  onClick={() => { setQuery(sq); handleSearch(sq); }}
                  className="text-xs px-3 py-1.5 rounded-full bg-slate-100 text-slate-600 hover:bg-blue-50 hover:text-blue-600 transition-colors"
                >
                  {sq}
                </button>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Error */}
      {error && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-red-600">
              <AlertTriangle size={18} />
              <span>{error}</span>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-4">
          {/* Answer Summary */}
          <Card className={`border ${getConfidenceBg(result.confidence)}`}>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg flex items-center gap-2">
                  <BookOpen size={20} />
                  {language === 'ar' ? result.answer_ar : result.answer?.substring(0, 120)}...
                </CardTitle>
                <div className={`text-sm font-bold ${getConfidenceColor(result.confidence)}`}>
                  {t('regsearch.confidence')}: {(result.confidence * 100).toFixed(0)}%
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-slate-700 mb-4">
                {language === 'ar' ? result.answer_ar : result.answer}
              </p>

              {/* Metadata badges */}
              <div className="flex flex-wrap gap-2 mb-3">
                <Badge variant="info">
                  {t('regsearch.results')}: {result.total_results}
                </Badge>
                {result.retrieval_methods_used.map((method) => (
                  <Badge key={method} variant="secondary">
                    {method}
                  </Badge>
                ))}
                {result.topics_matched.map((topic) => (
                  <Badge key={topic} variant="outline">
                    {topic}
                  </Badge>
                ))}
              </div>

              {/* Gaps */}
              {result.gaps_detected.length > 0 && (
                <div className="mt-3 p-3 bg-amber-50 rounded-lg border border-amber-200">
                  <p className="text-xs font-semibold text-amber-700 mb-1">{t('regsearch.gaps')}:</p>
                  {result.gaps_detected.map((gap, i) => (
                    <p key={i} className="text-xs text-amber-600">{gap}</p>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Citations */}
          {result.citations.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider">
                {t('regsearch.results')} ({result.citations.length})
              </h3>

              {result.citations.map((citation, index) => (
                <Card key={index} className="hover:shadow-md transition-shadow">
                  <CardContent className="pt-5 pb-4">
                    {/* Top row: source + badges */}
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <Scale size={14} className="text-slate-400" />
                          <span className="font-semibold text-sm text-slate-800">
                            {language === 'ar' ? citation.source_title_ar || citation.source_title : citation.source_title}
                          </span>
                          {citation.source_url && (
                            <a
                              href={citation.source_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-blue-500 hover:text-blue-700"
                            >
                              <ExternalLink size={12} />
                            </a>
                          )}
                        </div>
                        <div className="flex flex-wrap gap-1.5 text-xs">
                          <Badge variant={citation.is_binding ? 'success' : 'warning'}>
                            {citation.is_binding ? t('regsearch.binding') : t('regsearch.non_binding')}
                          </Badge>
                          <Badge variant="info">{citation.regulator_abbreviation}</Badge>
                          <Badge variant="secondary">{citation.jurisdiction}</Badge>
                          <Badge variant="outline">{getTierLabel(citation.authority_level)}</Badge>
                        </div>
                      </div>
                      <div className="text-right ms-4">
                        <div className={`text-sm font-bold ${getConfidenceColor(citation.relevance_score * 3)}`}>
                          {(citation.relevance_score * 100).toFixed(1)}%
                        </div>
                        <div className="text-xs text-slate-400">{t('regsearch.relevance')}</div>
                      </div>
                    </div>

                    {/* Provision section */}
                    {citation.provision_section && (
                      <div className="text-xs text-slate-500 mb-1">
                        {t('regsearch.provision')}: {citation.provision_section} — {citation.provision_title}
                      </div>
                    )}

                    {/* Expandable provision text */}
                    <button
                      onClick={() => toggleCitation(index)}
                      className="flex items-center gap-1 text-xs text-blue-500 hover:text-blue-700 mt-1"
                    >
                      {expandedCitations.has(index) ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                      {expandedCitations.has(index) ? 'Collapse' : 'Show provision text'}
                    </button>

                    {expandedCitations.has(index) && (
                      <div className="mt-2 p-3 bg-slate-50 rounded-lg text-sm text-slate-700 border">
                        {language === 'ar' && citation.provision_text_ar
                          ? citation.provision_text_ar
                          : citation.provision_text}
                      </div>
                    )}

                    {/* Retrieval method */}
                    <div className="mt-2 text-xs text-slate-400">
                      {t('regsearch.methods_used')}: {citation.retrieval_method}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}

          {/* No results */}
          {result.citations.length === 0 && (
            <Card>
              <CardContent className="pt-6 text-center text-slate-500">
                <Info size={24} className="mx-auto mb-2" />
                {t('regsearch.no_results')}
              </CardContent>
            </Card>
          )}

          {/* Disclaimer */}
          <div className="text-xs text-slate-400 italic text-center">
            {language === 'ar' ? result.disclaimer_ar : result.disclaimer || t('regsearch.disclaimer')}
          </div>
        </div>
      )}
    </div>
  );
}
