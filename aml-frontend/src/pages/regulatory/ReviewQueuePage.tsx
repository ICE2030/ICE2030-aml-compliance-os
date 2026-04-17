import { useState, useEffect, useCallback } from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import {
  CheckCircle2, XCircle, RotateCcw, FileText, Zap, Filter,
  ChevronDown, ChevronUp, Loader2,
} from 'lucide-react';
import api from '@/services/api';

interface ObligationItem {
  id: string;
  text: string;
  text_ar?: string;
  normalized_summary?: string;
  normalized_summary_ar?: string;
  obligation_type: string;
  applies_to_entity_types?: string[];
  condition?: string;
  deadline?: string;
  confidence: number;
  extraction_method: string;
  review_status: string;
  reviewer_notes?: string;
  version: number;
  provision_id?: string;
  provision_section?: string;
  provision_title?: string;
  provision_title_ar?: string;
  regulator_name?: string;
  regulator_abbreviation?: string;
  jurisdiction_name?: string;
  jurisdiction_code?: string;
  created_at?: string;
}

interface ReviewStats {
  total_obligations: number;
  by_status: Record<string, number>;
  by_type: Record<string, number>;
  by_extraction_method: Record<string, number>;
  average_confidence: number;
  total_review_decisions: number;
}

export default function ReviewQueuePage() {
  const { t, language } = useLanguage();
  const [obligations, setObligations] = useState<ObligationItem[]>([]);
  const [stats, setStats] = useState<ReviewStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [extracting, setExtracting] = useState(false);
  const [total, setTotal] = useState(0);
  const [statusFilter, setStatusFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [methodFilter, setMethodFilter] = useState('');
  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set());
  const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set());
  const [reviewNotes, setReviewNotes] = useState<Record<string, string>>({});
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const fetchObligations = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = { limit: '50' };
      if (statusFilter) params.review_status = statusFilter;
      if (typeFilter) params.obligation_type = typeFilter;
      if (methodFilter) params.extraction_method = methodFilter;

      const response = await api.get('/api/regulatory/obligations', { params });
      setObligations(response.data.items || []);
      setTotal(response.data.total || 0);
    } catch (err) {
      console.error('Failed to fetch obligations:', err);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, typeFilter, methodFilter]);

  const fetchStats = useCallback(async () => {
    try {
      const response = await api.get('/api/regulatory/review-stats');
      setStats(response.data);
    } catch (err) {
      console.error('Failed to fetch stats:', err);
    }
  }, []);

  useEffect(() => {
    fetchObligations();
    fetchStats();
  }, [fetchObligations, fetchStats]);

  const handleExtractAll = async () => {
    setExtracting(true);
    try {
      await api.post('/api/regulatory/obligations/extract-all');
      await fetchObligations();
      await fetchStats();
    } catch (err) {
      console.error('Extraction failed:', err);
    } finally {
      setExtracting(false);
    }
  };

  const handleReview = async (obligationId: string, decision: string) => {
    setActionLoading(obligationId);
    try {
      await api.post(`/api/regulatory/obligations/${obligationId}/review`, {
        decision,
        reviewer_notes: reviewNotes[obligationId] || undefined,
      });
      await fetchObligations();
      await fetchStats();
    } catch (err) {
      console.error('Review failed:', err);
    } finally {
      setActionLoading(null);
    }
  };

  const handleBatchReview = async (decision: string) => {
    if (selectedItems.size === 0) return;
    setActionLoading('batch');
    try {
      await api.post('/api/regulatory/obligations/batch-review', {
        obligation_ids: Array.from(selectedItems),
        decision,
      });
      setSelectedItems(new Set());
      await fetchObligations();
      await fetchStats();
    } catch (err) {
      console.error('Batch review failed:', err);
    } finally {
      setActionLoading(null);
    }
  };

  const toggleExpand = (id: string) => {
    setExpandedItems(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelect = (id: string) => {
    setSelectedItems(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedItems.size === obligations.length) {
      setSelectedItems(new Set());
    } else {
      setSelectedItems(new Set(obligations.map(o => o.id)));
    }
  };

  const getStatusBadge = (status: string) => {
    const map: Record<string, { variant: 'warning' | 'success' | 'danger' | 'info'; label: string }> = {
      pending: { variant: 'warning', label: t('review.pending') },
      approved: { variant: 'success', label: t('review.approved') },
      rejected: { variant: 'danger', label: t('review.rejected') },
      needs_revision: { variant: 'info', label: t('review.needs_revision') },
    };
    const config = map[status] || { variant: 'secondary' as any, label: status };
    return <Badge variant={config.variant}>{config.label}</Badge>;
  };

  const getTypeBadge = (type: string) => {
    const map: Record<string, string> = {
      mandatory: t('review.mandatory'),
      prohibition: t('review.prohibition'),
      reporting: t('review.reporting'),
      threshold: t('review.threshold'),
      governance: t('review.governance'),
      deadline: t('review.deadline') || 'Deadline',
      recordkeeping: 'Recordkeeping',
    };
    return <Badge variant="outline">{map[type] || type}</Badge>;
  };

  const getMethodBadge = (method: string) => {
    const map: Record<string, string> = {
      rule_based: t('review.rule_based'),
      ai_extracted: t('review.ai_extracted'),
      hybrid: t('review.hybrid'),
      manual: t('review.manual'),
    };
    return <Badge variant="secondary">{map[method] || method}</Badge>;
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return 'text-emerald-600 bg-emerald-50';
    if (confidence >= 0.6) return 'text-amber-600 bg-amber-50';
    return 'text-red-500 bg-red-50';
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">{t('review.title')}</h1>
          <p className="text-slate-500 mt-1">{t('review.subtitle')}</p>
        </div>
        <Button
          onClick={handleExtractAll}
          disabled={extracting}
          className="bg-blue-600 hover:bg-blue-700"
        >
          {extracting ? (
            <>
              <Loader2 size={16} className="me-2 animate-spin" />
              {t('review.extracting')}
            </>
          ) : (
            <>
              <Zap size={16} className="me-2" />
              {t('review.extract_all')}
            </>
          )}
        </Button>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <Card>
            <CardContent className="pt-5 pb-4 text-center">
              <div className="text-2xl font-bold text-slate-800">{stats.total_obligations}</div>
              <div className="text-xs text-slate-500">{t('review.total')}</div>
            </CardContent>
          </Card>
          <Card className="border-amber-200 bg-amber-50">
            <CardContent className="pt-5 pb-4 text-center">
              <div className="text-2xl font-bold text-amber-600">{stats.by_status?.pending || 0}</div>
              <div className="text-xs text-amber-600">{t('review.pending')}</div>
            </CardContent>
          </Card>
          <Card className="border-emerald-200 bg-emerald-50">
            <CardContent className="pt-5 pb-4 text-center">
              <div className="text-2xl font-bold text-emerald-600">{stats.by_status?.approved || 0}</div>
              <div className="text-xs text-emerald-600">{t('review.approved')}</div>
            </CardContent>
          </Card>
          <Card className="border-red-200 bg-red-50">
            <CardContent className="pt-5 pb-4 text-center">
              <div className="text-2xl font-bold text-red-600">{stats.by_status?.rejected || 0}</div>
              <div className="text-xs text-red-600">{t('review.rejected')}</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-5 pb-4 text-center">
              <div className="text-2xl font-bold text-blue-600">{(stats.average_confidence * 100).toFixed(0)}%</div>
              <div className="text-xs text-slate-500">{t('review.avg_confidence')}</div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Filters */}
      <Card>
        <CardContent className="pt-5 pb-4">
          <div className="flex items-center gap-3 flex-wrap">
            <Filter size={16} className="text-slate-400" />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white"
            >
              <option value="">{t('review.filter_status')}</option>
              <option value="pending">{t('review.pending')}</option>
              <option value="approved">{t('review.approved')}</option>
              <option value="rejected">{t('review.rejected')}</option>
              <option value="needs_revision">{t('review.needs_revision')}</option>
            </select>
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white"
            >
              <option value="">{t('review.filter_type')}</option>
              <option value="mandatory">{t('review.mandatory')}</option>
              <option value="prohibition">{t('review.prohibition')}</option>
              <option value="reporting">{t('review.reporting')}</option>
              <option value="threshold">{t('review.threshold')}</option>
              <option value="governance">{t('review.governance')}</option>
            </select>
            <select
              value={methodFilter}
              onChange={(e) => setMethodFilter(e.target.value)}
              className="border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white"
            >
              <option value="">{t('review.filter_method')}</option>
              <option value="rule_based">{t('review.rule_based')}</option>
              <option value="ai_extracted">{t('review.ai_extracted')}</option>
              <option value="hybrid">{t('review.hybrid')}</option>
            </select>

            {/* Batch actions */}
            {selectedItems.size > 0 && (
              <div className="ms-auto flex gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={toggleSelectAll}
                >
                  {selectedItems.size === obligations.length ? 'Deselect All' : t('review.select_all')}
                </Button>
                <Button
                  size="sm"
                  className="bg-emerald-600 hover:bg-emerald-700"
                  onClick={() => handleBatchReview('approved')}
                  disabled={actionLoading === 'batch'}
                >
                  <CheckCircle2 size={14} className="me-1" />
                  {t('review.batch_approve')} ({selectedItems.size})
                </Button>
                <Button
                  size="sm"
                  variant="destructive"
                  onClick={() => handleBatchReview('rejected')}
                  disabled={actionLoading === 'batch'}
                >
                  <XCircle size={14} className="me-1" />
                  {t('review.batch_reject')} ({selectedItems.size})
                </Button>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Loading */}
      {loading && (
        <div className="text-center py-12">
          <Loader2 size={32} className="mx-auto animate-spin text-blue-600" />
          <p className="text-slate-500 mt-3">{t('common.loading')}</p>
        </div>
      )}

      {/* Empty state */}
      {!loading && obligations.length === 0 && (
        <Card>
          <CardContent className="pt-8 pb-8 text-center">
            <FileText size={48} className="mx-auto text-slate-300 mb-4" />
            <p className="text-slate-500">{t('review.no_obligations')}</p>
          </CardContent>
        </Card>
      )}

      {/* Obligation List */}
      {!loading && obligations.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-sm text-slate-500">
              {total} {t('review.total').toLowerCase()}
            </p>
            <Button size="sm" variant="ghost" onClick={toggleSelectAll}>
              {selectedItems.size === obligations.length ? 'Deselect All' : t('review.select_all')}
            </Button>
          </div>

          {obligations.map((ob) => (
            <Card
              key={ob.id}
              className={`transition-all ${selectedItems.has(ob.id) ? 'ring-2 ring-blue-400' : ''}`}
            >
              <CardContent className="pt-5 pb-4">
                {/* Top row */}
                <div className="flex items-start gap-3">
                  {/* Checkbox */}
                  <input
                    type="checkbox"
                    checked={selectedItems.has(ob.id)}
                    onChange={() => toggleSelect(ob.id)}
                    className="mt-1.5 h-4 w-4 rounded border-slate-300"
                  />

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    {/* Badges row */}
                    <div className="flex flex-wrap gap-1.5 mb-2">
                      {getStatusBadge(ob.review_status)}
                      {getTypeBadge(ob.obligation_type)}
                      {getMethodBadge(ob.extraction_method)}
                      <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-semibold ${getConfidenceColor(ob.confidence)}`}>
                        {(ob.confidence * 100).toFixed(0)}%
                      </span>
                    </div>

                    {/* Text */}
                    <p className="text-sm text-slate-800 line-clamp-2">
                      {language === 'ar' && ob.text_ar ? ob.text_ar : ob.text}
                    </p>

                    {/* Provision ref */}
                    {ob.provision_section && (
                      <div className="mt-1 text-xs text-slate-500">
                        {t('review.provision_ref')}: {ob.provision_section} — {
                          language === 'ar' && ob.provision_title_ar ? ob.provision_title_ar : ob.provision_title
                        }
                        {ob.regulator_abbreviation && (
                          <span className="ms-2 text-blue-500">[{ob.regulator_abbreviation}]</span>
                        )}
                      </div>
                    )}

                    {/* Expandable details */}
                    <button
                      onClick={() => toggleExpand(ob.id)}
                      className="flex items-center gap-1 text-xs text-blue-500 hover:text-blue-700 mt-2"
                    >
                      {expandedItems.has(ob.id) ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                      {expandedItems.has(ob.id) ? 'Collapse' : 'Details'}
                    </button>

                    {expandedItems.has(ob.id) && (
                      <div className="mt-3 p-3 bg-slate-50 rounded-lg text-sm space-y-2 border">
                        {ob.applies_to_entity_types && ob.applies_to_entity_types.length > 0 && (
                          <div>
                            <span className="font-medium text-slate-600">{t('review.applies_to')}:</span>{' '}
                            <span className="text-slate-700">{ob.applies_to_entity_types.join(', ')}</span>
                          </div>
                        )}
                        {ob.condition && (
                          <div>
                            <span className="font-medium text-slate-600">{t('review.condition')}:</span>{' '}
                            <span className="text-slate-700">{ob.condition}</span>
                          </div>
                        )}
                        {ob.deadline && (
                          <div>
                            <span className="font-medium text-slate-600">{t('review.deadline')}:</span>{' '}
                            <span className="text-slate-700">{ob.deadline}</span>
                          </div>
                        )}
                        {ob.reviewer_notes && (
                          <div>
                            <span className="font-medium text-slate-600">{t('review.notes')}:</span>{' '}
                            <span className="text-slate-700">{ob.reviewer_notes}</span>
                          </div>
                        )}

                        {/* Review notes input */}
                        <div className="pt-2 border-t">
                          <Input
                            placeholder={t('review.notes_placeholder')}
                            value={reviewNotes[ob.id] || ''}
                            onChange={(e) => setReviewNotes(prev => ({ ...prev, [ob.id]: e.target.value }))}
                            className="text-sm"
                          />
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Action buttons */}
                  <div className="flex flex-col gap-1.5 ms-3">
                    <Button
                      size="sm"
                      className="bg-emerald-600 hover:bg-emerald-700 text-xs px-3"
                      onClick={() => handleReview(ob.id, 'approved')}
                      disabled={actionLoading === ob.id}
                    >
                      <CheckCircle2 size={14} className="me-1" />
                      {t('review.approve')}
                    </Button>
                    <Button
                      size="sm"
                      variant="destructive"
                      className="text-xs px-3"
                      onClick={() => handleReview(ob.id, 'rejected')}
                      disabled={actionLoading === ob.id}
                    >
                      <XCircle size={14} className="me-1" />
                      {t('review.reject')}
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="text-xs px-3"
                      onClick={() => handleReview(ob.id, 'needs_revision')}
                      disabled={actionLoading === ob.id}
                    >
                      <RotateCcw size={14} className="me-1" />
                      {t('review.request_revision')}
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
