import { useState, useEffect, useCallback } from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import api from '@/services/api';
import { Button } from '@/components/ui/button';
import { FileText, Plus, Trash2, ChevronDown, ChevronUp, ArrowRight } from 'lucide-react';

interface Evidence {
  id: string;
  name: string;
  name_ar?: string;
  description?: string;
  description_ar?: string;
  artifact_type: string;
  source_system?: string;
  collection_method?: string;
  periodicity?: string;
  owner?: string;
  status: string;
  control_id: string;
  control_name?: string;
}

interface ChainLink {
  evidence: { id: string; name: string };
  control: { id: string; name: string };
  obligations: Array<{ id: string; text: string; obligation_type: string }>;
  provisions: Array<{ id: string; title: string; article_number: string }>;
  sources: Array<{ id: string; title: string; regulator: string }>;
}

export default function EvidencePage() {
  const { t, language } = useLanguage();
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [chain, setChain] = useState<ChainLink | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [controls, setControls] = useState<Array<{ id: string; name: string }>>([]);
  const [filterType, setFilterType] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [form, setForm] = useState({
    control_id: '', name: '', name_ar: '', description: '', description_ar: '',
    artifact_type: 'document', source_system: '', collection_method: 'manual',
    periodicity: 'monthly', owner: '', status: 'active',
  });

  const loadEvidence = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (filterType) params.artifact_type = filterType;
      if (filterStatus) params.status = filterStatus;
      const res = await api.get('/api/phase4/evidence', { params });
      setEvidence(res.data.items || []);
      setTotal(res.data.total || 0);
    } catch { /* ignore */ }
    setLoading(false);
  }, [filterType, filterStatus]);

  useEffect(() => { loadEvidence(); }, [loadEvidence]);

  useEffect(() => {
    api.get('/api/phase4/controls', { params: { limit: 200 } })
      .then(res => setControls(res.data.items?.map((c: { id: string; name: string }) => ({ id: c.id, name: c.name })) || []))
      .catch(() => {});
  }, []);

  const loadChain = async (evidenceId: string) => {
    if (expandedId === evidenceId) { setExpandedId(null); return; }
    try {
      const res = await api.get(`/api/phase4/evidence/${evidenceId}/chain`);
      setChain(res.data);
      setExpandedId(evidenceId);
    } catch { setChain(null); setExpandedId(evidenceId); }
  };

  const handleCreate = async () => {
    try {
      await api.post('/api/phase4/evidence', form);
      setShowCreate(false);
      setForm({ control_id: '', name: '', name_ar: '', description: '', description_ar: '', artifact_type: 'document', source_system: '', collection_method: 'manual', periodicity: 'monthly', owner: '', status: 'active' });
      loadEvidence();
    } catch { /* ignore */ }
  };

  const handleDelete = async (id: string) => {
    if (!confirm(t('common.confirm'))) return;
    try { await api.delete(`/api/phase4/evidence/${id}`); loadEvidence(); } catch { /* ignore */ }
  };

  const artifactTypes = ['document', 'log', 'attestation', 'report', 'screenshot', 'certificate', 'policy_doc', 'training_record', 'system_output'];
  const statusList = ['active', 'expired', 'under_review', 'archived'];
  const typeColors: Record<string, string> = {
    document: 'bg-blue-100 text-blue-800', log: 'bg-slate-100 text-slate-700',
    attestation: 'bg-purple-100 text-purple-800', report: 'bg-green-100 text-green-800',
    screenshot: 'bg-amber-100 text-amber-800', certificate: 'bg-teal-100 text-teal-800',
    policy_doc: 'bg-indigo-100 text-indigo-800', training_record: 'bg-pink-100 text-pink-800',
    system_output: 'bg-cyan-100 text-cyan-800',
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <FileText className="text-green-600" size={28} />
            {t('p4.evidence_title')}
          </h1>
          <p className="text-slate-500 mt-1">{t('p4.evidence_subtitle')}</p>
        </div>
        <Button onClick={() => setShowCreate(!showCreate)} className="gap-2">
          <Plus size={16} /> {t('p4.create_evidence')}
        </Button>
      </div>

      {/* Create form */}
      {showCreate && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
          <h3 className="font-semibold text-lg">{t('p4.create_evidence')}</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium text-slate-700">{t('p4.linked_control')}</label>
              <select className="w-full mt-1 px-3 py-2 border rounded-lg" value={form.control_id} onChange={e => setForm({...form, control_id: e.target.value})}>
                <option value="">{t('p4.select_control')}</option>
                {controls.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700">{t('p4.evidence_type')}</label>
              <select className="w-full mt-1 px-3 py-2 border rounded-lg" value={form.artifact_type} onChange={e => setForm({...form, artifact_type: e.target.value})}>
                {artifactTypes.map(at => <option key={at} value={at}>{t(`p4.etype_${at}`)}</option>)}
              </select>
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700">{t('p4.evidence_name')} (EN)</label>
              <input className="w-full mt-1 px-3 py-2 border rounded-lg" value={form.name} onChange={e => setForm({...form, name: e.target.value})} />
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700">{t('p4.evidence_name')} (AR)</label>
              <input className="w-full mt-1 px-3 py-2 border rounded-lg" dir="rtl" value={form.name_ar} onChange={e => setForm({...form, name_ar: e.target.value})} />
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700">{t('p4.source_system')}</label>
              <input className="w-full mt-1 px-3 py-2 border rounded-lg" value={form.source_system} onChange={e => setForm({...form, source_system: e.target.value})} />
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700">{t('p4.collection_method')}</label>
              <select className="w-full mt-1 px-3 py-2 border rounded-lg" value={form.collection_method} onChange={e => setForm({...form, collection_method: e.target.value})}>
                <option value="manual">{t('p4.method_manual')}</option>
                <option value="automated">{t('p4.method_automated')}</option>
                <option value="semi_automated">{t('p4.method_semi_automated')}</option>
                <option value="system_generated">{t('p4.method_system_generated')}</option>
              </select>
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700">{t('p4.periodicity')}</label>
              <input className="w-full mt-1 px-3 py-2 border rounded-lg" value={form.periodicity} onChange={e => setForm({...form, periodicity: e.target.value})} />
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700">{t('p4.owner')}</label>
              <input className="w-full mt-1 px-3 py-2 border rounded-lg" value={form.owner} onChange={e => setForm({...form, owner: e.target.value})} />
            </div>
          </div>
          <div className="flex gap-2 pt-2">
            <Button onClick={handleCreate} disabled={!form.name || !form.control_id}>{t('common.save')}</Button>
            <Button variant="outline" onClick={() => setShowCreate(false)}>{t('common.cancel')}</Button>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-3 flex-wrap">
        <select className="px-3 py-2 border rounded-lg text-sm" value={filterType} onChange={e => setFilterType(e.target.value)}>
          <option value="">{t('p4.all_types')}</option>
          {artifactTypes.map(at => <option key={at} value={at}>{t(`p4.etype_${at}`)}</option>)}
        </select>
        <select className="px-3 py-2 border rounded-lg text-sm" value={filterStatus} onChange={e => setFilterStatus(e.target.value)}>
          <option value="">{t('p4.all_statuses')}</option>
          {statusList.map(s => <option key={s} value={s}>{t(`p4.estatus_${s}`)}</option>)}
        </select>
        <span className="text-sm text-slate-500 self-center">{total} {t('p4.evidence_items')}</span>
      </div>

      {/* Evidence list */}
      {loading ? (
        <div className="text-center py-12 text-slate-400">{t('common.loading')}</div>
      ) : evidence.length === 0 ? (
        <div className="text-center py-12 bg-white rounded-xl border">
          <FileText className="mx-auto text-slate-300" size={48} />
          <p className="text-slate-500 mt-3">{t('p4.no_evidence')}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {evidence.map(ev => (
            <div key={ev.id} className="bg-white rounded-xl border border-slate-200 overflow-hidden">
              <div className="p-4">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3">
                      <h3 className="font-semibold text-slate-900">
                        {language === 'ar' && ev.name_ar ? ev.name_ar : ev.name}
                      </h3>
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${typeColors[ev.artifact_type] || 'bg-slate-100'}`}>
                        {t(`p4.etype_${ev.artifact_type}`)}
                      </span>
                    </div>
                    <p className="text-sm text-slate-500 mt-1">
                      {language === 'ar' && ev.description_ar ? ev.description_ar : ev.description}
                    </p>
                    <div className="flex gap-4 mt-2 text-xs text-slate-400">
                      {ev.source_system && <span>{t('p4.source_system')}: {ev.source_system}</span>}
                      {ev.collection_method && <span>{t('p4.collection_method')}: {t(`p4.method_${ev.collection_method}`) || ev.collection_method}</span>}
                      {ev.periodicity && <span>{t('p4.periodicity')}: {ev.periodicity}</span>}
                      {ev.owner && <span>{t('p4.owner')}: {ev.owner}</span>}
                    </div>
                  </div>
                  <div className="flex gap-1">
                    <Button variant="ghost" size="icon" onClick={() => loadChain(ev.id)} title={t('p4.view_chain')}>
                      {expandedId === ev.id ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                    </Button>
                    <Button variant="ghost" size="icon" onClick={() => handleDelete(ev.id)}>
                      <Trash2 size={16} className="text-red-400" />
                    </Button>
                  </div>
                </div>
              </div>

              {/* Chain view */}
              {expandedId === ev.id && chain && (
                <div className="border-t bg-slate-50 p-4">
                  <h4 className="text-sm font-medium text-slate-700 mb-3">{t('p4.provenance_chain')}</h4>
                  <div className="flex items-center gap-2 flex-wrap text-sm">
                    {/* Sources */}
                    {chain.sources?.map((s, i) => (
                      <span key={i} className="bg-blue-100 text-blue-800 px-3 py-1 rounded-lg">
                        {s.title} ({s.regulator})
                      </span>
                    ))}
                    {chain.sources?.length > 0 && <ArrowRight size={16} className="text-slate-400" />}
                    {/* Provisions */}
                    {chain.provisions?.map((p, i) => (
                      <span key={i} className="bg-purple-100 text-purple-800 px-3 py-1 rounded-lg">
                        {p.article_number}: {p.title?.substring(0, 40)}
                      </span>
                    ))}
                    {chain.provisions?.length > 0 && <ArrowRight size={16} className="text-slate-400" />}
                    {/* Obligations */}
                    {chain.obligations?.map((o, i) => (
                      <span key={i} className="bg-amber-100 text-amber-800 px-3 py-1 rounded-lg">
                        [{o.obligation_type}] {o.text?.substring(0, 50)}...
                      </span>
                    ))}
                    {chain.obligations?.length > 0 && <ArrowRight size={16} className="text-slate-400" />}
                    {/* Control */}
                    <span className="bg-green-100 text-green-800 px-3 py-1 rounded-lg">
                      {chain.control?.name}
                    </span>
                    <ArrowRight size={16} className="text-slate-400" />
                    {/* Evidence */}
                    <span className="bg-teal-100 text-teal-800 px-3 py-1 rounded-lg font-medium">
                      {chain.evidence?.name}
                    </span>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
