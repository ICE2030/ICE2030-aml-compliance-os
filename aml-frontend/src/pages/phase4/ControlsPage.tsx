import { useState, useEffect, useCallback } from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import api from '@/services/api';
import { Button } from '@/components/ui/button';
import { Shield, Plus, Link2, Trash2, ChevronDown, ChevronUp, FileText } from 'lucide-react';

interface Control {
  id: string;
  name: string;
  name_ar?: string;
  description?: string;
  description_ar?: string;
  control_type: string;
  owner?: string;
  frequency?: string;
  status: string;
  obligation_count: number;
  evidence_count: number;
  regulator_id?: string;
}

interface Obligation {
  id: string;
  text: string;
  obligation_type: string;
  review_status: string;
}

export default function ControlsPage() {
  const { t, language } = useLanguage();
  const [controls, setControls] = useState<Control[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [obligations, setObligations] = useState<Obligation[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [filterType, setFilterType] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [form, setForm] = useState({
    name: '', name_ar: '', description: '', description_ar: '',
    control_type: 'policy', owner: '', frequency: 'continuous', status: 'draft',
  });

  const loadControls = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (filterType) params.control_type = filterType;
      if (filterStatus) params.status = filterStatus;
      const res = await api.get('/api/phase4/controls', { params });
      setControls(res.data.items || []);
      setTotal(res.data.total || 0);
    } catch { /* ignore */ }
    setLoading(false);
  }, [filterType, filterStatus]);

  useEffect(() => { loadControls(); }, [loadControls]);

  const loadObligations = async (controlId: string) => {
    if (expandedId === controlId) { setExpandedId(null); return; }
    try {
      const res = await api.get(`/api/phase4/controls/${controlId}/obligations`);
      setObligations(res.data || []);
      setExpandedId(controlId);
    } catch { setObligations([]); setExpandedId(controlId); }
  };

  const handleCreate = async () => {
    try {
      await api.post('/api/phase4/controls', form);
      setShowCreate(false);
      setForm({ name: '', name_ar: '', description: '', description_ar: '', control_type: 'policy', owner: '', frequency: 'continuous', status: 'draft' });
      loadControls();
    } catch { /* ignore */ }
  };

  const handleDelete = async (id: string) => {
    if (!confirm(t('common.confirm'))) return;
    try { await api.delete(`/api/phase4/controls/${id}`); loadControls(); } catch { /* ignore */ }
  };

  const controlTypes = ['policy', 'procedure', 'technical', 'monitoring', 'training'];
  const statuses = ['draft', 'active', 'under_review', 'retired'];
  const typeColors: Record<string, string> = {
    policy: 'bg-blue-100 text-blue-800', procedure: 'bg-purple-100 text-purple-800',
    technical: 'bg-green-100 text-green-800', monitoring: 'bg-amber-100 text-amber-800',
    training: 'bg-pink-100 text-pink-800',
  };
  const statusColors: Record<string, string> = {
    draft: 'bg-slate-100 text-slate-700', active: 'bg-green-100 text-green-800',
    under_review: 'bg-amber-100 text-amber-800', retired: 'bg-red-100 text-red-800',
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <Shield className="text-blue-600" size={28} />
            {t('p4.controls_title')}
          </h1>
          <p className="text-slate-500 mt-1">{t('p4.controls_subtitle')}</p>
        </div>
        <Button onClick={() => setShowCreate(!showCreate)} className="gap-2">
          <Plus size={16} /> {t('p4.create_control')}
        </Button>
      </div>

      {/* Create form */}
      {showCreate && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
          <h3 className="font-semibold text-lg">{t('p4.create_control')}</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium text-slate-700">{t('p4.control_name')} (EN)</label>
              <input className="w-full mt-1 px-3 py-2 border rounded-lg" value={form.name} onChange={e => setForm({...form, name: e.target.value})} />
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700">{t('p4.control_name')} (AR)</label>
              <input className="w-full mt-1 px-3 py-2 border rounded-lg" dir="rtl" value={form.name_ar} onChange={e => setForm({...form, name_ar: e.target.value})} />
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700">{t('p4.description')} (EN)</label>
              <textarea className="w-full mt-1 px-3 py-2 border rounded-lg" rows={2} value={form.description} onChange={e => setForm({...form, description: e.target.value})} />
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700">{t('p4.description')} (AR)</label>
              <textarea className="w-full mt-1 px-3 py-2 border rounded-lg" dir="rtl" rows={2} value={form.description_ar} onChange={e => setForm({...form, description_ar: e.target.value})} />
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700">{t('p4.control_type')}</label>
              <select className="w-full mt-1 px-3 py-2 border rounded-lg" value={form.control_type} onChange={e => setForm({...form, control_type: e.target.value})}>
                {controlTypes.map(ct => <option key={ct} value={ct}>{t(`p4.type_${ct}`)}</option>)}
              </select>
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700">{t('p4.owner')}</label>
              <input className="w-full mt-1 px-3 py-2 border rounded-lg" value={form.owner} onChange={e => setForm({...form, owner: e.target.value})} />
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700">{t('p4.frequency')}</label>
              <select className="w-full mt-1 px-3 py-2 border rounded-lg" value={form.frequency} onChange={e => setForm({...form, frequency: e.target.value})}>
                <option value="continuous">{t('p4.freq_continuous')}</option>
                <option value="daily">{t('p4.freq_daily')}</option>
                <option value="weekly">{t('p4.freq_weekly')}</option>
                <option value="monthly">{t('p4.freq_monthly')}</option>
                <option value="quarterly">{t('p4.freq_quarterly')}</option>
                <option value="annual">{t('p4.freq_annual')}</option>
                <option value="per-transaction">{t('p4.freq_per_transaction')}</option>
              </select>
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700">{t('p4.status')}</label>
              <select className="w-full mt-1 px-3 py-2 border rounded-lg" value={form.status} onChange={e => setForm({...form, status: e.target.value})}>
                {statuses.map(s => <option key={s} value={s}>{t(`p4.status_${s}`)}</option>)}
              </select>
            </div>
          </div>
          <div className="flex gap-2 pt-2">
            <Button onClick={handleCreate} disabled={!form.name}>{t('common.save')}</Button>
            <Button variant="outline" onClick={() => setShowCreate(false)}>{t('common.cancel')}</Button>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-3 flex-wrap">
        <select className="px-3 py-2 border rounded-lg text-sm" value={filterType} onChange={e => setFilterType(e.target.value)}>
          <option value="">{t('p4.all_types')}</option>
          {controlTypes.map(ct => <option key={ct} value={ct}>{t(`p4.type_${ct}`)}</option>)}
        </select>
        <select className="px-3 py-2 border rounded-lg text-sm" value={filterStatus} onChange={e => setFilterStatus(e.target.value)}>
          <option value="">{t('p4.all_statuses')}</option>
          {statuses.map(s => <option key={s} value={s}>{t(`p4.status_${s}`)}</option>)}
        </select>
        <span className="text-sm text-slate-500 self-center">{total} {t('p4.controls_count')}</span>
      </div>

      {/* Controls list */}
      {loading ? (
        <div className="text-center py-12 text-slate-400">{t('common.loading')}</div>
      ) : controls.length === 0 ? (
        <div className="text-center py-12 bg-white rounded-xl border">
          <Shield className="mx-auto text-slate-300" size={48} />
          <p className="text-slate-500 mt-3">{t('p4.no_controls')}</p>
          <p className="text-sm text-slate-400 mt-1">{t('p4.seed_hint')}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {controls.map(ctrl => (
            <div key={ctrl.id} className="bg-white rounded-xl border border-slate-200 overflow-hidden">
              <div className="p-4">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3">
                      <h3 className="font-semibold text-slate-900">
                        {language === 'ar' && ctrl.name_ar ? ctrl.name_ar : ctrl.name}
                      </h3>
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${typeColors[ctrl.control_type] || 'bg-slate-100'}`}>
                        {t(`p4.type_${ctrl.control_type}`)}
                      </span>
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusColors[ctrl.status] || 'bg-slate-100'}`}>
                        {t(`p4.status_${ctrl.status}`)}
                      </span>
                    </div>
                    <p className="text-sm text-slate-500 mt-1">
                      {language === 'ar' && ctrl.description_ar ? ctrl.description_ar : ctrl.description}
                    </p>
                    <div className="flex gap-4 mt-2 text-xs text-slate-400">
                      {ctrl.owner && <span>{t('p4.owner')}: {ctrl.owner}</span>}
                      {ctrl.frequency && <span>{t('p4.frequency')}: {t(`p4.freq_${ctrl.frequency}`) || ctrl.frequency}</span>}
                      <span className="flex items-center gap-1"><Link2 size={12} /> {ctrl.obligation_count} {t('p4.obligations')}</span>
                      <span className="flex items-center gap-1"><FileText size={12} /> {ctrl.evidence_count} {t('p4.evidence_items')}</span>
                    </div>
                  </div>
                  <div className="flex gap-1">
                    <Button variant="ghost" size="icon" onClick={() => loadObligations(ctrl.id)}>
                      {expandedId === ctrl.id ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                    </Button>
                    <Button variant="ghost" size="icon" onClick={() => handleDelete(ctrl.id)}>
                      <Trash2 size={16} className="text-red-400" />
                    </Button>
                  </div>
                </div>
              </div>

              {/* Expanded: linked obligations */}
              {expandedId === ctrl.id && (
                <div className="border-t bg-slate-50 p-4">
                  <h4 className="text-sm font-medium text-slate-700 mb-2">{t('p4.linked_obligations')} ({obligations.length})</h4>
                  {obligations.length === 0 ? (
                    <p className="text-sm text-slate-400">{t('p4.no_linked_obligations')}</p>
                  ) : (
                    <div className="space-y-2">
                      {obligations.map((ob: Obligation) => (
                        <div key={ob.id} className="bg-white p-3 rounded-lg border text-sm">
                          <p className="text-slate-800">{ob.text?.substring(0, 200)}{(ob.text?.length || 0) > 200 ? '...' : ''}</p>
                          <div className="flex gap-2 mt-1 text-xs text-slate-400">
                            <span className="bg-slate-100 px-2 py-0.5 rounded">{ob.obligation_type}</span>
                            <span className="bg-slate-100 px-2 py-0.5 rounded">{ob.review_status}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
