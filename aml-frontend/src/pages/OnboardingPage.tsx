import { useEffect, useState } from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import api from '@/services/api';
import { Plus, Search, Building2, User, Eye, X } from 'lucide-react';

interface Entity {
  id: string;
  name: string;
  name_ar: string | null;
  entity_type: string;
  onboarding_status: string;
  risk_level: string | null;
  risk_score: number | null;
  country: string;
  national_id: string | null;
  registration_number: string | null;
  industry: string | null;
  created_at: string;
}

const statusColors: Record<string, string> = {
  draft: 'secondary', pending_review: 'warning', under_review: 'info',
  approved: 'success', rejected: 'danger', requires_info: 'warning',
};

const riskColors: Record<string, string> = {
  low: 'success', medium: 'warning', high: 'danger', critical: 'destructive',
};

export default function OnboardingPage() {
  const { t } = useLanguage();
  const [entities, setEntities] = useState<Entity[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [search, setSearch] = useState('');
  const [selectedEntity, setSelectedEntity] = useState<Entity | null>(null);
  const [form, setForm] = useState({
    entity_type: 'company', name: '', name_ar: '', national_id: '',
    registration_number: '', country: 'SA', industry: '', phone: '', email: '',
  });

  const loadEntities = () => {
    setLoading(true);
    api.get('/api/onboarding/entities').then(res => {
      setEntities(Array.isArray(res.data) ? res.data : []);
    }).catch(() => setEntities([])).finally(() => setLoading(false));
  };

  useEffect(() => { loadEntities(); }, []);

  const createEntity = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.post('/api/onboarding/entities', form);
      setShowCreate(false);
      setForm({ entity_type: 'company', name: '', name_ar: '', national_id: '', registration_number: '', country: 'SA', industry: '', phone: '', email: '' });
      loadEntities();
    } catch (err) {
      console.error('Failed to create entity', err);
    }
  };

  const reviewEntity = async (entityId: string, status: string, reasoning: string) => {
    try {
      await api.post(`/api/onboarding/entities/${entityId}/review`, {
        decision: status, reasoning, confidence_level: 0.8,
      });
      loadEntities();
      setSelectedEntity(null);
    } catch (err) {
      console.error('Failed to review entity', err);
    }
  };

  const filtered = entities.filter(e =>
    e.name.toLowerCase().includes(search.toLowerCase()) ||
    (e.registration_number || '').toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{t('nav.onboarding')}</h1>
          <p className="text-slate-500 text-sm">KYB/KYC Entity Onboarding & Review</p>
        </div>
        <Button onClick={() => setShowCreate(true)} className="bg-blue-600 hover:bg-blue-700">
          <Plus size={16} className="me-2" /> {t('entity.create')}
        </Button>
      </div>

      {/* Search */}
      <div className="flex gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
          <Input placeholder={t('common.search')} value={search} onChange={e => setSearch(e.target.value)} className="ps-9" />
        </div>
      </div>

      {/* Create Modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <Card className="w-full max-w-lg max-h-[90vh] overflow-auto">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>{t('entity.create')}</CardTitle>
              <Button variant="ghost" size="icon" onClick={() => setShowCreate(false)}><X size={18} /></Button>
            </CardHeader>
            <CardContent>
              <form onSubmit={createEntity} className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm font-medium">{t('entity.type')}</label>
                    <Select value={form.entity_type} onChange={e => setForm({ ...form, entity_type: e.target.value })}>
                      <option value="company">{t('entity.company')}</option>
                      <option value="individual">{t('entity.individual')}</option>
                    </Select>
                  </div>
                  <div>
                    <label className="text-sm font-medium">Country</label>
                    <Select value={form.country} onChange={e => setForm({ ...form, country: e.target.value })}>
                      <option value="SA">Saudi Arabia</option>
                      <option value="AE">UAE</option>
                      <option value="BH">Bahrain</option>
                      <option value="KW">Kuwait</option>
                      <option value="QA">Qatar</option>
                      <option value="OM">Oman</option>
                    </Select>
                  </div>
                </div>
                <div>
                  <label className="text-sm font-medium">{t('entity.name')} (English)</label>
                  <Input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required />
                </div>
                <div>
                  <label className="text-sm font-medium">{t('entity.name')} (Arabic)</label>
                  <Input value={form.name_ar} onChange={e => setForm({ ...form, name_ar: e.target.value })} dir="rtl" />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm font-medium">National ID / Iqama</label>
                    <Input value={form.national_id} onChange={e => setForm({ ...form, national_id: e.target.value })} />
                  </div>
                  <div>
                    <label className="text-sm font-medium">Registration No.</label>
                    <Input value={form.registration_number} onChange={e => setForm({ ...form, registration_number: e.target.value })} />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm font-medium">Industry</label>
                    <Input value={form.industry} onChange={e => setForm({ ...form, industry: e.target.value })} />
                  </div>
                  <div>
                    <label className="text-sm font-medium">Email</label>
                    <Input type="email" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} />
                  </div>
                </div>
                <div className="flex justify-end gap-2 pt-2">
                  <Button type="button" variant="outline" onClick={() => setShowCreate(false)}>{t('common.cancel')}</Button>
                  <Button type="submit" className="bg-blue-600 hover:bg-blue-700">{t('common.save')}</Button>
                </div>
              </form>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Entity Detail */}
      {selectedEntity && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <Card className="w-full max-w-2xl max-h-[90vh] overflow-auto">
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  {selectedEntity.entity_type === 'company' ? <Building2 size={20} /> : <User size={20} />}
                  {selectedEntity.name}
                </CardTitle>
                <p className="text-sm text-slate-500 mt-1">{selectedEntity.name_ar}</p>
              </div>
              <Button variant="ghost" size="icon" onClick={() => setSelectedEntity(null)}><X size={18} /></Button>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div><span className="text-sm text-slate-500">Type:</span> <span className="font-medium capitalize">{selectedEntity.entity_type}</span></div>
                <div><span className="text-sm text-slate-500">Country:</span> <span className="font-medium">{selectedEntity.country}</span></div>
                <div><span className="text-sm text-slate-500">Status:</span> <Badge variant={(statusColors[selectedEntity.onboarding_status] || 'secondary') as "success" | "warning" | "info" | "danger" | "destructive" | "secondary"}>{selectedEntity.onboarding_status.replace('_', ' ')}</Badge></div>
                <div><span className="text-sm text-slate-500">Risk:</span> {selectedEntity.risk_level && <Badge variant={(riskColors[selectedEntity.risk_level] || 'secondary') as "success" | "warning" | "danger" | "destructive"}>{selectedEntity.risk_level}</Badge>}</div>
                <div><span className="text-sm text-slate-500">Risk Score:</span> <span className="font-medium">{selectedEntity.risk_score ?? 'N/A'}</span></div>
                <div><span className="text-sm text-slate-500">Industry:</span> <span className="font-medium">{selectedEntity.industry || 'N/A'}</span></div>
              </div>
              {selectedEntity.onboarding_status === 'pending_review' && (
                <div className="border-t pt-4 space-y-3">
                  <h4 className="font-medium">Review Decision</h4>
                  <div className="flex gap-2">
                    <Button variant="success" onClick={() => reviewEntity(selectedEntity.id, 'approved', 'Entity meets all KYB requirements')}>
                      Approve
                    </Button>
                    <Button variant="destructive" onClick={() => reviewEntity(selectedEntity.id, 'rejected', 'Entity does not meet compliance requirements')}>
                      Reject
                    </Button>
                    <Button variant="warning" onClick={() => reviewEntity(selectedEntity.id, 'requires_info', 'Additional documentation required')}>
                      Request Info
                    </Button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* Entity List */}
      {loading ? (
        <p className="text-slate-500">{t('common.loading')}</p>
      ) : (
        <div className="grid gap-4">
          {filtered.length === 0 ? (
            <Card><CardContent className="p-8 text-center text-slate-500">{t('common.no_data')}</CardContent></Card>
          ) : (
            <div className="bg-white rounded-xl border shadow overflow-hidden">
              <table className="w-full">
                <thead className="bg-slate-50 border-b">
                  <tr>
                    <th className="text-start p-3 text-sm font-medium text-slate-600">{t('entity.name')}</th>
                    <th className="text-start p-3 text-sm font-medium text-slate-600">{t('entity.type')}</th>
                    <th className="text-start p-3 text-sm font-medium text-slate-600">Country</th>
                    <th className="text-start p-3 text-sm font-medium text-slate-600">{t('entity.status')}</th>
                    <th className="text-start p-3 text-sm font-medium text-slate-600">{t('entity.risk_level')}</th>
                    <th className="text-start p-3 text-sm font-medium text-slate-600">{t('common.actions')}</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map(entity => (
                    <tr key={entity.id} className="border-b hover:bg-slate-50 transition-colors">
                      <td className="p-3">
                        <div className="flex items-center gap-2">
                          {entity.entity_type === 'company' ? <Building2 size={16} className="text-slate-400" /> : <User size={16} className="text-slate-400" />}
                          <div>
                            <p className="font-medium text-sm">{entity.name}</p>
                            {entity.name_ar && <p className="text-xs text-slate-500" dir="rtl">{entity.name_ar}</p>}
                          </div>
                        </div>
                      </td>
                      <td className="p-3 text-sm capitalize">{entity.entity_type}</td>
                      <td className="p-3 text-sm">{entity.country}</td>
                      <td className="p-3">
                        <Badge variant={(statusColors[entity.onboarding_status] || 'secondary') as "success" | "warning" | "info" | "danger" | "destructive" | "secondary"}>
                          {entity.onboarding_status.replace('_', ' ')}
                        </Badge>
                      </td>
                      <td className="p-3">
                        {entity.risk_level ? (
                          <Badge variant={(riskColors[entity.risk_level] || 'secondary') as "success" | "warning" | "danger" | "destructive"}>
                            {entity.risk_level} ({entity.risk_score?.toFixed(0)})
                          </Badge>
                        ) : '-'}
                      </td>
                      <td className="p-3">
                        <Button variant="ghost" size="sm" onClick={() => setSelectedEntity(entity)}>
                          <Eye size={14} className="me-1" /> {t('common.view')}
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
