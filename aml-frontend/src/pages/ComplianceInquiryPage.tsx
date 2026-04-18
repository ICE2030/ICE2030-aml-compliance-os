import { useEffect, useState } from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Select } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import api from '@/services/api';
import { BookOpen, Search, ExternalLink, Building2, Landmark, Filter, MessageSquare, AlertTriangle } from 'lucide-react';

interface Regulation {
  id: string;
  source: string;
  title: string;
  category: string;
  summary: string;
  key_requirements: string[];
  penalties?: string;
  reference_url?: string;
  relevance_score?: number;
}

interface InquiryResponse {
  answer: string;
  regulations: Regulation[];
  sources: { name: string; regulation: string; url?: string }[];
  disclaimer: string;
}

interface Category {
  id: string;
  name: string;
  name_ar: string;
}

export default function ComplianceInquiryPage() {
  const { t, language } = useLanguage();
  const [question, setQuestion] = useState('');
  const [source, setSource] = useState('all');
  const [category, setCategory] = useState('');
  const [inquiryResult, setInquiryResult] = useState<InquiryResponse | null>(null);
  const [regulations, setRegulations] = useState<{ sama: Regulation[]; cma: Regulation[] }>({ sama: [], cma: [] });
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(false);
  const [browsing, setBrowsing] = useState(false);
  const [activeTab, setActiveTab] = useState<'inquiry' | 'browse'>('inquiry');

  useEffect(() => {
    api.get('/api/compliance/categories').then(res => {
      setCategories(Array.isArray(res.data) ? res.data : []);
    }).catch(() => {});
  }, []);

  const submitInquiry = async () => {
    if (!question.trim()) return;
    setLoading(true);
    setInquiryResult(null);
    try {
      const res = await api.post('/api/compliance/inquiry', {
        question: question.trim(),
        source,
        language,
      });
      setInquiryResult(res.data);
    } catch (err) {
      console.error('Inquiry failed', err);
    } finally {
      setLoading(false);
    }
  };

  const browseRegulations = async () => {
    setBrowsing(true);
    try {
      const res = await api.get('/api/compliance/regulations', {
        params: { source, language, category: category || undefined },
      });
      if (res.data) {
        setRegulations({
          sama: res.data.sama?.regulations || [],
          cma: res.data.cma?.regulations || [],
        });
      }
    } catch (err) {
      console.error('Browse failed', err);
    } finally {
      setBrowsing(false);
    }
  };

  useEffect(() => { browseRegulations(); }, [source, category, language]);

  const categoryLabels: Record<string, string> = {};
  categories.forEach(c => {
    categoryLabels[c.id] = language === 'ar' ? c.name_ar : c.name;
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{t('compliance.title')}</h1>
          <p className="text-slate-500 text-sm">{t('compliance.subtitle')}</p>
        </div>
      </div>

      {/* Source Selector Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="border-purple-200 bg-purple-50/50 cursor-pointer hover:shadow-md transition-shadow"
              onClick={() => setSource(source === 'sama' ? 'all' : 'sama')}>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-purple-100 rounded-lg">
                <Landmark size={20} className="text-purple-700" />
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold text-sm text-purple-900">{t('compliance.sama_title')}</h3>
                  {source === 'sama' || source === 'all' ? <Badge variant="info">{t('compliance.active')}</Badge> : null}
                </div>
                <p className="text-xs text-purple-700 mt-0.5">{t('compliance.sama_desc')}</p>
                <a href="https://rulebook.sama.gov.sa" target="_blank" rel="noopener noreferrer"
                   className="text-xs text-purple-600 hover:underline inline-flex items-center gap-1 mt-1"
                   onClick={e => e.stopPropagation()}>
                  rulebook.sama.gov.sa <ExternalLink size={10} />
                </a>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="border-teal-200 bg-teal-50/50 cursor-pointer hover:shadow-md transition-shadow"
              onClick={() => setSource(source === 'cma' ? 'all' : 'cma')}>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-teal-100 rounded-lg">
                <Building2 size={20} className="text-teal-700" />
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold text-sm text-teal-900">{t('compliance.cma_title')}</h3>
                  {source === 'cma' || source === 'all' ? <Badge variant="info">{t('compliance.active')}</Badge> : null}
                </div>
                <p className="text-xs text-teal-700 mt-0.5">{t('compliance.cma_desc')}</p>
                <a href="https://cma.org.sa" target="_blank" rel="noopener noreferrer"
                   className="text-xs text-teal-600 hover:underline inline-flex items-center gap-1 mt-1"
                   onClick={e => e.stopPropagation()}>
                  cma.org.sa <ExternalLink size={10} />
                </a>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tab Switcher */}
      <div className="flex gap-2 border-b">
        <button
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${activeTab === 'inquiry' ? 'border-blue-600 text-blue-600' : 'border-transparent text-slate-500 hover:text-slate-700'}`}
          onClick={() => setActiveTab('inquiry')}
        >
          <MessageSquare size={14} className="inline me-1.5" />
          {t('compliance.ask_question')}
        </button>
        <button
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${activeTab === 'browse' ? 'border-blue-600 text-blue-600' : 'border-transparent text-slate-500 hover:text-slate-700'}`}
          onClick={() => setActiveTab('browse')}
        >
          <BookOpen size={14} className="inline me-1.5" />
          {t('compliance.browse_regulations')}
        </button>
      </div>

      {/* Inquiry Tab */}
      {activeTab === 'inquiry' && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <MessageSquare size={20} /> {t('compliance.ask_question')}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Textarea
                value={question}
                onChange={e => setQuestion(e.target.value)}
                placeholder={language === 'ar' ? 'اكتب سؤالك عن اللوائح التنظيمية هنا...' : 'Type your regulatory compliance question here...'}
                rows={3}
                className="text-base"
              />
            </div>
            <div className="flex gap-3 items-center">
              <Select value={source} onChange={e => setSource(e.target.value)} className="w-48">
                <option value="all">{t('compliance.all_sources')}</option>
                <option value="sama">{t('compliance.sama_only')}</option>
                <option value="cma">{t('compliance.cma_only')}</option>
              </Select>
              <Button onClick={submitInquiry} disabled={!question.trim() || loading} className="bg-blue-600 hover:bg-blue-700">
                <Search size={16} className="me-2" />
                {loading ? t('common.loading') : t('compliance.submit_inquiry')}
              </Button>
            </div>

            {/* Inquiry Result */}
            {inquiryResult && (
              <div className="space-y-4 mt-4">
                <div className="bg-slate-50 rounded-lg p-4">
                  <h4 className="font-semibold text-sm mb-2">{t('compliance.answer')}</h4>
                  <div className="text-sm text-slate-700 whitespace-pre-line">{inquiryResult.answer}</div>
                </div>

                {inquiryResult.sources.length > 0 && (
                  <div className="bg-blue-50 rounded-lg p-4">
                    <h4 className="font-semibold text-sm mb-2 text-blue-900">{t('compliance.sources')}</h4>
                    <ul className="space-y-1">
                      {inquiryResult.sources.map((src, i) => (
                        <li key={i} className="text-sm text-blue-800 flex items-center gap-2">
                          <span className="font-medium">{src.name}:</span> {src.regulation}
                          {src.url && (
                            <a href={src.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                              <ExternalLink size={12} />
                            </a>
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="flex items-start gap-2 bg-amber-50 border border-amber-200 rounded-lg p-3">
                  <AlertTriangle size={16} className="text-amber-600 mt-0.5 shrink-0" />
                  <p className="text-xs text-amber-800">{inquiryResult.disclaimer}</p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Browse Tab */}
      {activeTab === 'browse' && (
        <div className="space-y-4">
          <div className="flex gap-3 items-center">
            <Filter size={16} className="text-slate-400" />
            <Select value={category} onChange={e => setCategory(e.target.value)} className="w-64">
              <option value="">{t('compliance.all_categories')}</option>
              {categories.map(c => (
                <option key={c.id} value={c.id}>{language === 'ar' ? c.name_ar : c.name}</option>
              ))}
            </Select>
          </div>

          {browsing ? (
            <p className="text-slate-500">{t('common.loading')}</p>
          ) : (
            <div className="space-y-6">
              {/* SAMA Regulations */}
              {regulations.sama.length > 0 && (
                <div>
                  <h3 className="text-lg font-semibold flex items-center gap-2 mb-3">
                    <Landmark size={18} className="text-purple-600" />
                    {t('compliance.sama_regulations')}
                  </h3>
                  <div className="space-y-3">
                    {regulations.sama.map(reg => (
                      <Card key={reg.id} className="hover:shadow-md transition-shadow">
                        <CardContent className="p-4">
                          <div className="flex items-start justify-between">
                            <div className="flex-1">
                              <div className="flex items-center gap-2 mb-1">
                                <h4 className="font-semibold text-sm">{reg.title}</h4>
                                <Badge variant="secondary">{categoryLabels[reg.category] || reg.category}</Badge>
                              </div>
                              <p className="text-sm text-slate-600 mb-2">{reg.summary}</p>
                              {reg.key_requirements.length > 0 && (
                                <div className="mt-2">
                                  <p className="text-xs font-medium text-slate-500 mb-1">{t('compliance.key_requirements')}:</p>
                                  <ul className="text-xs text-slate-600 space-y-0.5">
                                    {reg.key_requirements.slice(0, 4).map((req, i) => (
                                      <li key={i} className="flex items-start gap-1.5">
                                        <span className="text-blue-500 mt-0.5">•</span> {req}
                                      </li>
                                    ))}
                                    {reg.key_requirements.length > 4 && (
                                      <li className="text-slate-400">+{reg.key_requirements.length - 4} {t('compliance.more')}</li>
                                    )}
                                  </ul>
                                </div>
                              )}
                            </div>
                            {reg.reference_url && (
                              <a href={reg.reference_url} target="_blank" rel="noopener noreferrer"
                                 className="text-blue-600 hover:text-blue-800 shrink-0 ms-3">
                                <ExternalLink size={16} />
                              </a>
                            )}
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </div>
              )}

              {/* CMA Regulations */}
              {regulations.cma.length > 0 && (
                <div>
                  <h3 className="text-lg font-semibold flex items-center gap-2 mb-3">
                    <Building2 size={18} className="text-teal-600" />
                    {t('compliance.cma_regulations')}
                  </h3>
                  <div className="space-y-3">
                    {regulations.cma.map(reg => (
                      <Card key={reg.id} className="hover:shadow-md transition-shadow">
                        <CardContent className="p-4">
                          <div className="flex items-start justify-between">
                            <div className="flex-1">
                              <div className="flex items-center gap-2 mb-1">
                                <h4 className="font-semibold text-sm">{reg.title}</h4>
                                <Badge variant="secondary">{categoryLabels[reg.category] || reg.category}</Badge>
                              </div>
                              <p className="text-sm text-slate-600 mb-2">{reg.summary}</p>
                              {reg.key_requirements.length > 0 && (
                                <div className="mt-2">
                                  <p className="text-xs font-medium text-slate-500 mb-1">{t('compliance.key_requirements')}:</p>
                                  <ul className="text-xs text-slate-600 space-y-0.5">
                                    {reg.key_requirements.slice(0, 4).map((req, i) => (
                                      <li key={i} className="flex items-start gap-1.5">
                                        <span className="text-teal-500 mt-0.5">•</span> {req}
                                      </li>
                                    ))}
                                    {reg.key_requirements.length > 4 && (
                                      <li className="text-slate-400">+{reg.key_requirements.length - 4} {t('compliance.more')}</li>
                                    )}
                                  </ul>
                                </div>
                              )}
                            </div>
                            {reg.reference_url && (
                              <a href={reg.reference_url} target="_blank" rel="noopener noreferrer"
                                 className="text-teal-600 hover:text-teal-800 shrink-0 ms-3">
                                <ExternalLink size={16} />
                              </a>
                            )}
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </div>
              )}

              {regulations.sama.length === 0 && regulations.cma.length === 0 && (
                <Card><CardContent className="p-8 text-center text-slate-500">{t('common.no_data')}</CardContent></Card>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
