import { useState, useEffect } from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { FileText, RefreshCw, Edit3, Trash2, AlertTriangle, CheckCircle, Info } from 'lucide-react';
import { EmptyState } from '@/components/EmptyState';
import { trackUsage } from '@/hooks/useUsageTracking';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface NarrativeSummary {
  id: string;
  title: string;
  title_ar?: string;
  narrative_type: string;
  sections: Record<string, unknown>;
  health_indicators: Record<string, string>;
  top_exposures: Array<{ area: string; details: string }>;
  generated_from: Record<string, unknown>;
  ai_model: string;
  confidence_note?: string;
  is_ai_generated: boolean;
  is_editable: boolean;
  edited_by?: string;
  edited_at?: string;
  created_at?: string;
}

export default function NarrativePage() {
  const { language, t } = useLanguage();
  const [narratives, setNarratives] = useState<NarrativeSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [editSections, setEditSections] = useState<string>('');

  const token = localStorage.getItem('token');
  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  const fetchNarratives = () => {
    setLoading(true);
    fetch(`${API}/api/grc/narratives`, { headers })
      .then(r => r.json())
      .then(data => setNarratives(data.items || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchNarratives(); }, []);

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const res = await fetch(`${API}/api/grc/narratives/generate`, { method: 'POST', headers });
      if (res.ok) {
        const created = await res.json().catch(() => ({} as { id?: string }));
        trackUsage('create', { resource_type: 'narrative', resource_id: created?.id, path: '/grc/narratives' });
        fetchNarratives();
      }
    } catch { /* ignore */ }
    setGenerating(false);
  };

  const handleEdit = (narrative: NarrativeSummary) => {
    if (editId === narrative.id) {
      setEditId(null);
      return;
    }
    setEditId(narrative.id);
    setEditSections(JSON.stringify(narrative.sections, null, 2));
  };

  const handleSaveEdit = async (id: string) => {
    try {
      const sections = JSON.parse(editSections);
      await fetch(`${API}/api/grc/narratives/${id}`, {
        method: 'PUT', headers, body: JSON.stringify({ sections }),
      });
      trackUsage('update', { resource_type: 'narrative', resource_id: id, path: '/grc/narratives' });
      setEditId(null);
      fetchNarratives();
    } catch { /* invalid JSON */ }
  };

  const handleDelete = async (id: string) => {
    await fetch(`${API}/api/grc/narratives/${id}`, { method: 'DELETE', headers });
    trackUsage('delete', { resource_type: 'narrative', resource_id: id, path: '/grc/narratives' });
    fetchNarratives();
  };

  const healthColor = (status: string) => {
    switch (status) {
      case 'critical': return 'bg-red-100 text-red-800 border-red-300';
      case 'elevated': return 'bg-orange-100 text-orange-800 border-orange-300';
      case 'manageable': return 'bg-yellow-100 text-yellow-800 border-yellow-300';
      case 'healthy': return 'bg-green-100 text-green-800 border-green-300';
      default: return 'bg-slate-100 text-slate-800';
    }
  };

  const healthIcon = (status: string) => {
    switch (status) {
      case 'critical': return <AlertTriangle size={14} className="text-red-600" />;
      case 'elevated': return <AlertTriangle size={14} className="text-orange-600" />;
      case 'manageable': return <Info size={14} className="text-yellow-600" />;
      case 'healthy': return <CheckCircle size={14} className="text-green-600" />;
      default: return <Info size={14} />;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            {language === 'ar' ? 'الملخصات التنفيذية' : 'Executive Narratives'}
          </h1>
          <p className="text-slate-500 mt-1">
            {language === 'ar' ? 'ملخصات تنفيذية مولّدة بالقواعد — قابلة للتعديل وليست موثوقة' : 'Rule-based AI-generated executive summaries — editable, not authoritative'}
          </p>
        </div>
        <Button onClick={handleGenerate} disabled={generating}>
          <RefreshCw size={16} className={`me-2 ${generating ? 'animate-spin' : ''}`} />
          {generating
            ? (language === 'ar' ? 'جاري التوليد...' : 'Generating...')
            : (language === 'ar' ? 'توليد ملخص جديد' : 'Generate Summary')}
        </Button>
      </div>

      {/* AI Disclaimer */}
      <Card className="bg-amber-50 border-amber-200">
        <CardContent className="py-3 px-4">
          <div className="flex items-center gap-2 text-sm text-amber-800">
            <AlertTriangle size={16} />
            <span className="font-medium">
              {language === 'ar'
                ? 'تنبيه: هذه الملخصات مولّدة بقواعد آلية وليست موثوقة. راجعها قبل الاعتماد عليها.'
                : 'Notice: These summaries are rule-based AI-generated and not authoritative. Review before relying on them.'}
            </span>
          </div>
        </CardContent>
      </Card>

      {/* Narratives */}
      {loading ? (
        <div className="flex items-center justify-center h-32"><div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" /></div>
      ) : narratives.length === 0 ? (
        <EmptyState
          icon={<FileText size={48} />}
          title={t('empty.narratives_title')}
          hint={t('empty.narratives_hint')}
          primaryAction={
            <Button onClick={handleGenerate} disabled={generating}>
              <RefreshCw size={16} className={`me-2 ${generating ? 'animate-spin' : ''}`} />
              {generating
                ? (language === 'ar' ? 'جاري التوليد...' : 'Generating...')
                : (language === 'ar' ? 'توليد ملخص جديد' : 'Generate Summary')}
            </Button>
          }
          showLoadSamples
          onSamplesLoaded={fetchNarratives}
        />
      ) : (
        <div className="space-y-6">
          {narratives.map(narrative => (
            <Card key={narrative.id} className="border-slate-200">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center gap-2">
                    <FileText size={20} className="text-blue-500" />
                    {language === 'ar' && narrative.title_ar ? narrative.title_ar : narrative.title}
                  </CardTitle>
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="text-xs">
                      {narrative.ai_model} | {language === 'ar' ? 'مولّد بالذكاء الاصطناعي' : 'AI-Generated'}
                    </Badge>
                    {narrative.edited_by && (
                      <Badge className="text-xs bg-purple-100 text-purple-800">
                        {language === 'ar' ? 'معدّل' : 'Edited'}
                      </Badge>
                    )}
                    <Button variant="ghost" size="sm" onClick={() => handleEdit(narrative)}>
                      <Edit3 size={14} />
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => handleDelete(narrative.id)} className="text-red-500">
                      <Trash2 size={14} />
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Health Indicators */}
                {narrative.health_indicators && Object.keys(narrative.health_indicators).length > 0 && (
                  <div>
                    <h4 className="text-sm font-semibold text-slate-700 mb-2">
                      {language === 'ar' ? 'مؤشرات الصحة' : 'Health Indicators'}
                    </h4>
                    <div className="flex gap-2 flex-wrap">
                      {Object.entries(narrative.health_indicators).map(([area, status]) => (
                        <Badge key={area} className={`text-xs ${healthColor(status as string)}`}>
                          {healthIcon(status as string)}
                          <span className="ms-1">{area}: {status as string}</span>
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}

                {/* Sections */}
                {narrative.sections && Object.keys(narrative.sections).length > 0 && (
                  <div className="space-y-3">
                    {Object.entries(narrative.sections).map(([key, value]) => (
                      <div key={key} className="border rounded-lg p-3">
                        <h4 className="text-sm font-semibold text-slate-700 capitalize mb-1">{key.replace(/_/g, ' ')}</h4>
                        <p className="text-sm text-slate-600">
                          {typeof value === 'string' ? value : JSON.stringify(value)}
                        </p>
                      </div>
                    ))}
                  </div>
                )}

                {/* Top Exposures */}
                {narrative.top_exposures && narrative.top_exposures.length > 0 && (
                  <div>
                    <h4 className="text-sm font-semibold text-slate-700 mb-2">
                      {language === 'ar' ? 'أهم التعرضات' : 'Top Exposures'}
                    </h4>
                    <div className="space-y-1">
                      {narrative.top_exposures.map((exp, i) => (
                        <div key={i} className="flex items-center gap-2 text-sm">
                          <AlertTriangle size={12} className="text-red-500 shrink-0" />
                          <span className="font-medium">{exp.area}:</span>
                          <span className="text-slate-600">{exp.details}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Edit Panel */}
                {editId === narrative.id && (
                  <div className="border-t pt-4 space-y-2">
                    <h4 className="text-sm font-semibold text-slate-700">
                      {language === 'ar' ? 'تعديل الأقسام (JSON)' : 'Edit Sections (JSON)'}
                    </h4>
                    <textarea
                      className="w-full border rounded-md p-2 text-xs font-mono"
                      rows={10}
                      value={editSections}
                      onChange={e => setEditSections(e.target.value)}
                    />
                    <div className="flex gap-2">
                      <Button size="sm" onClick={() => handleSaveEdit(narrative.id)}>
                        {language === 'ar' ? 'حفظ التعديلات' : 'Save Changes'}
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => setEditId(null)}>
                        {language === 'ar' ? 'إلغاء' : 'Cancel'}
                      </Button>
                    </div>
                  </div>
                )}

                {/* Confidence Note */}
                {narrative.confidence_note && (
                  <p className="text-xs text-slate-400 italic">{narrative.confidence_note}</p>
                )}

                {/* Footer */}
                <div className="text-xs text-slate-400 flex items-center gap-4">
                  {narrative.created_at && <span>{language === 'ar' ? 'تم التوليد' : 'Generated'}: {new Date(narrative.created_at).toLocaleString()}</span>}
                  {narrative.edited_at && <span>{language === 'ar' ? 'آخر تعديل' : 'Last edited'}: {new Date(narrative.edited_at).toLocaleString()}</span>}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
