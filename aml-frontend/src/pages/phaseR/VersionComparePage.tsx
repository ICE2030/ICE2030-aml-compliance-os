import { useState, useEffect, useCallback } from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import api from '@/services/api';
import { Button } from '@/components/ui/button';
import { GitCompare, RefreshCw, FileText, ChevronDown, ChevronUp } from 'lucide-react';

interface DocumentOption {
  id: string;
  title: string;
  title_ar?: string;
}

interface ProvisionVersion {
  version: number;
  snapshot_id: string;
  snapshot_at: string;
  content_hash: string;
  text: string;
  text_ar?: string;
  title?: string;
  title_ar?: string;
  section_number?: string;
  provision_type?: string;
  diff_from_previous?: string;
}

interface ProvisionComparison {
  provision_id: string;
  section_number?: string;
  title?: string;
  title_ar?: string;
  versions: ProvisionVersion[];
  total_versions: number;
  has_changes: boolean;
}

export default function VersionComparePage() {
  const { t, language } = useLanguage();
  const [documents, setDocuments] = useState<DocumentOption[]>([]);
  const [selectedDoc, setSelectedDoc] = useState('');
  const [provisions, setProvisions] = useState<ProvisionComparison[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingDocs, setLoadingDocs] = useState(true);
  const [expandedProvision, setExpandedProvision] = useState<string>('');

  const loadDocuments = useCallback(async () => {
    setLoadingDocs(true);
    try {
      const res = await api.get('/api/regulatory/sources');
      const docs = (res.data?.items || []).map((s: { id: string; title: string; title_ar?: string }) => ({
        id: s.id,
        title: s.title,
        title_ar: s.title_ar,
      }));
      setDocuments(docs);
    } catch { /* ignore */ }
    setLoadingDocs(false);
  }, []);

  useEffect(() => { loadDocuments(); }, [loadDocuments]);

  const loadComparison = useCallback(async () => {
    if (!selectedDoc) return;
    setLoading(true);
    try {
      const res = await api.get(`/api/phase-r/versions/document/${selectedDoc}`);
      setProvisions(res.data.provisions || []);
    } catch { /* ignore */ }
    setLoading(false);
  }, [selectedDoc]);

  useEffect(() => { loadComparison(); }, [loadComparison]);

  const changedCount = provisions.filter(p => p.has_changes).length;
  const unchangedCount = provisions.filter(p => !p.has_changes).length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <GitCompare className="text-purple-600" size={28} />
            {t('pr.version_title')}
          </h1>
          <p className="text-slate-500 mt-1">{t('pr.version_subtitle')}</p>
        </div>
        {selectedDoc && (
          <Button onClick={loadComparison} variant="outline" className="gap-2">
            <RefreshCw size={16} /> {t('p4.refresh')}
          </Button>
        )}
      </div>

      {/* Document selector */}
      <div className="bg-white rounded-xl border border-slate-200 p-4">
        <label className="text-sm font-medium text-slate-700 block mb-2">{t('pr.select_document')}</label>
        {loadingDocs ? (
          <p className="text-sm text-slate-400">{t('common.loading')}</p>
        ) : (
          <select
            className="w-full px-3 py-2 border rounded-lg text-sm"
            value={selectedDoc}
            onChange={e => setSelectedDoc(e.target.value)}
          >
            <option value="">-- {t('pr.select_document')} --</option>
            {documents.map(doc => (
              <option key={doc.id} value={doc.id}>
                {language === 'ar' && doc.title_ar ? doc.title_ar : doc.title}
              </option>
            ))}
          </select>
        )}
      </div>

      {/* Summary */}
      {selectedDoc && !loading && provisions.length > 0 && (
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-amber-50 rounded-xl border border-amber-200 p-4 text-center">
            <p className="text-2xl font-bold text-amber-700">{changedCount}</p>
            <p className="text-xs text-amber-600">{t('pr.changed_provisions')}</p>
          </div>
          <div className="bg-green-50 rounded-xl border border-green-200 p-4 text-center">
            <p className="text-2xl font-bold text-green-700">{unchangedCount}</p>
            <p className="text-xs text-green-600">{t('pr.unchanged_provisions')}</p>
          </div>
        </div>
      )}

      {/* Provisions list */}
      {!selectedDoc ? null : loading ? (
        <div className="text-center py-12 text-slate-400">{t('common.loading')}</div>
      ) : provisions.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center">
          <FileText className="mx-auto text-slate-300 mb-3" size={32} />
          <p className="text-slate-500">{t('pr.no_versions')}</p>
          <p className="text-xs text-slate-400 mt-1">{t('pr.no_versions_hint')}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {provisions.filter(p => p.has_changes).map(prov => (
            <div key={prov.provision_id} className="bg-white rounded-xl border border-slate-200 overflow-hidden">
              <button
                className="w-full p-4 flex items-center justify-between text-left hover:bg-slate-50"
                onClick={() => setExpandedProvision(expandedProvision === prov.provision_id ? '' : prov.provision_id)}
              >
                <div className="flex items-center gap-3 flex-wrap">
                  <GitCompare size={16} className="text-amber-500" />
                  <span className="font-medium text-slate-900">
                    {prov.section_number && `${prov.section_number} — `}
                    {language === 'ar' && prov.title_ar ? prov.title_ar : prov.title || prov.provision_id}
                  </span>
                  <span className="text-xs text-slate-500">
                    {prov.total_versions} {t('pr.version').toLowerCase()}(s)
                  </span>
                  {prov.has_changes && (
                    <span className="px-2 py-0.5 rounded-full text-xs bg-amber-100 text-amber-700">
                      {t('pr.modified')}
                    </span>
                  )}
                </div>
                {expandedProvision === prov.provision_id ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
              </button>

              {expandedProvision === prov.provision_id && (
                <div className="border-t p-4 space-y-4">
                  {prov.versions.map((ver, idx) => (
                    <div key={ver.snapshot_id} className="border rounded-lg p-3">
                      <div className="flex items-center gap-3 mb-2 flex-wrap">
                        <span className="font-bold text-sm text-slate-800">
                          {t('pr.version')} {ver.version}
                        </span>
                        <span className="text-xs text-slate-400">
                          {new Date(ver.snapshot_at).toLocaleString()}
                        </span>
                        {ver.provision_type && (
                          <span className="px-2 py-0.5 rounded text-xs bg-slate-100 text-slate-600">
                            {ver.provision_type}
                          </span>
                        )}
                      </div>
                      <div className="text-sm text-slate-700 whitespace-pre-wrap bg-slate-50 rounded p-3 max-h-40 overflow-y-auto">
                        {language === 'ar' && ver.text_ar ? ver.text_ar : ver.text}
                      </div>
                      {idx > 0 && ver.diff_from_previous && (
                        <details className="mt-2">
                          <summary className="text-xs text-blue-600 cursor-pointer hover:underline">
                            {t('pr.diff')}
                          </summary>
                          <pre className="text-xs bg-slate-900 text-green-400 rounded p-3 mt-1 overflow-x-auto max-h-40">
                            {ver.diff_from_previous}
                          </pre>
                        </details>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}

          {/* Unchanged provisions collapsed */}
          {unchangedCount > 0 && (
            <div className="bg-slate-50 rounded-xl border border-slate-200 p-4 text-center text-sm text-slate-500">
              {unchangedCount} {t('pr.unchanged_provisions')}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
