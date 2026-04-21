import { useState, useEffect } from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  ShieldCheck, Download, Database, FileText, AlertTriangle,
  CheckCircle, Clock, Users, Lock,
} from 'lucide-react';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface IntegrityCheck {
  check: string;
  description: string;
  description_ar: string;
  total_checked: number;
  broken?: number;
  orphans?: number;
  status: string;
}

interface IntegrityReport {
  validated_at: string;
  total_checks: number;
  passed: number;
  failed: number;
  warnings: number;
  overall: string;
  checks: IntegrityCheck[];
}

interface ChainStats {
  chain: string;
  entity_counts: Record<string, number>;
  total_entities: number;
}

interface Permission {
  read: boolean;
  write: boolean;
}

interface RBACInfo {
  user_id: string;
  email: string;
  role: string;
  permissions: Record<string, Permission>;
}

interface AuditEntry {
  id: string;
  action: string;
  resource_type: string;
  resource_id: string;
  user_id: string;
  details: {
    prev_values?: Record<string, unknown>;
    new_values?: Record<string, unknown>;
    changed_fields?: string[];
    summary?: string;
    summary_ar?: string;
  };
  entry_hash: string;
  created_at: string;
}

export default function AdminPage() {
  const { language } = useLanguage();
  const [integrity, setIntegrity] = useState<IntegrityReport | null>(null);
  const [chainStats, setChainStats] = useState<ChainStats | null>(null);
  const [rbac, setRbac] = useState<RBACInfo | null>(null);
  const [auditTrail, setAuditTrail] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'integrity' | 'audit' | 'rbac' | 'exports'>('integrity');

  const token = localStorage.getItem('token');
  const headers = { Authorization: `Bearer ${token}` };

  const fetchIntegrity = async () => {
    setLoading(true);
    setError(null);
    try {
      const [intRes, chainRes] = await Promise.all([
        fetch(`${API}/api/grc/admin/integrity/validate`, { headers }),
        fetch(`${API}/api/grc/admin/integrity/chain-stats`, { headers }),
      ]);
      if (!intRes.ok) throw new Error(`Integrity check failed: ${intRes.status}`);
      if (!chainRes.ok) throw new Error(`Chain stats failed: ${chainRes.status}`);
      setIntegrity(await intRes.json());
      setChainStats(await chainRes.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load integrity data');
    } finally {
      setLoading(false);
    }
  };

  const fetchAuditTrail = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API}/api/grc/admin/audit-trail?limit=50`, { headers });
      if (!res.ok) throw new Error(`Audit trail failed: ${res.status}`);
      const data = await res.json();
      setAuditTrail(data.items || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load audit trail');
    } finally {
      setLoading(false);
    }
  };

  const fetchRBAC = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API}/api/grc/admin/rbac/permissions`, { headers });
      if (!res.ok) throw new Error(`RBAC check failed: ${res.status}`);
      setRbac(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load RBAC info');
    } finally {
      setLoading(false);
    }
  };

  const downloadCSV = async (type: string, filename: string) => {
    try {
      const res = await fetch(`${API}/api/grc/admin/export/${type}/csv`, { headers });
      if (!res.ok) throw new Error(`Export failed: ${res.status}`);
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Export failed');
    }
  };

  const downloadExecutiveReport = async () => {
    try {
      const res = await fetch(`${API}/api/grc/admin/export/executive-report`, { headers });
      if (!res.ok) throw new Error(`Export failed: ${res.status}`);
      const data = await res.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'executive_report.json';
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Export failed');
    }
  };

  useEffect(() => {
    if (activeTab === 'integrity') fetchIntegrity();
    else if (activeTab === 'audit') fetchAuditTrail();
    else if (activeTab === 'rbac') fetchRBAC();
  }, [activeTab]);

  const statusIcon = (status: string) => {
    if (status === 'pass') return <CheckCircle size={16} className="text-green-500" />;
    if (status === 'fail') return <AlertTriangle size={16} className="text-red-500" />;
    return <Clock size={16} className="text-yellow-500" />;
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">
          {language === 'ar' ? 'إدارة النظام والصلابة' : 'System Admin & Hardening'}
        </h1>
        <p className="text-slate-500 mt-1">
          {language === 'ar' ? 'سلامة البيانات، سجل التدقيق، الأدوار والصلاحيات، التصدير' : 'Data integrity, audit trail, RBAC, exports'}
        </p>
      </div>

      {/* Tab Navigation */}
      <div className="flex gap-2 border-b pb-2">
        {[
          { id: 'integrity' as const, label: language === 'ar' ? 'سلامة البيانات' : 'Data Integrity', icon: Database },
          { id: 'audit' as const, label: language === 'ar' ? 'سجل التدقيق' : 'Audit Trail', icon: FileText },
          { id: 'rbac' as const, label: language === 'ar' ? 'الأدوار والصلاحيات' : 'RBAC', icon: Users },
          { id: 'exports' as const, label: language === 'ar' ? 'التصدير' : 'Exports', icon: Download },
        ].map(tab => (
          <Button
            key={tab.id}
            variant={activeTab === tab.id ? 'default' : 'ghost'}
            size="sm"
            onClick={() => setActiveTab(tab.id)}
            className="flex items-center gap-2"
          >
            <tab.icon size={16} />
            {tab.label}
          </Button>
        ))}
      </div>

      {/* Error Banner */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-3">
          <AlertTriangle size={20} className="text-red-500 shrink-0" />
          <div>
            <p className="text-sm font-medium text-red-800">{language === 'ar' ? 'خطأ' : 'Error'}</p>
            <p className="text-sm text-red-600">{error}</p>
          </div>
          <Button variant="ghost" size="sm" onClick={() => setError(null)} className="ms-auto text-red-500">
            {language === 'ar' ? 'إغلاق' : 'Dismiss'}
          </Button>
        </div>
      )}

      {loading && (
        <div className="flex items-center justify-center h-32">
          <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
        </div>
      )}

      {/* Data Integrity Tab */}
      {activeTab === 'integrity' && !loading && (
        <div className="space-y-6">
          {/* Chain Stats */}
          {chainStats && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Database size={20} className="text-blue-500" />
                  {language === 'ar' ? 'إحصائيات سلسلة الكيانات' : 'Entity Chain Statistics'}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-xs text-slate-400 mb-3">{chainStats.chain}</p>
                <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
                  {Object.entries(chainStats.entity_counts).map(([key, count]) => (
                    <div key={key} className="text-center p-2 bg-slate-50 rounded-lg">
                      <p className="text-xl font-bold text-slate-900">{count}</p>
                      <p className="text-xs text-slate-500 capitalize">{key.replace(/_/g, ' ')}</p>
                    </div>
                  ))}
                </div>
                <div className="mt-3 text-right">
                  <Badge variant="outline">{language === 'ar' ? `الإجمالي: ${chainStats.total_entities}` : `Total: ${chainStats.total_entities}`}</Badge>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Integrity Report */}
          {integrity && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <ShieldCheck size={20} className={integrity.overall === 'healthy' ? 'text-green-500' : 'text-red-500'} />
                    {language === 'ar' ? 'تقرير سلامة البيانات' : 'Data Integrity Report'}
                  </div>
                  <div className="flex gap-2">
                    <Badge className="bg-green-100 text-green-800">{integrity.passed} {language === 'ar' ? 'ناجح' : 'passed'}</Badge>
                    {integrity.failed > 0 && <Badge variant="destructive">{integrity.failed} {language === 'ar' ? 'فشل' : 'failed'}</Badge>}
                    {integrity.warnings > 0 && <Badge className="bg-yellow-100 text-yellow-800">{integrity.warnings} {language === 'ar' ? 'تحذير' : 'warnings'}</Badge>}
                  </div>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {integrity.checks.map((check, idx) => (
                    <div key={idx} className="flex items-center justify-between border rounded-lg p-3">
                      <div className="flex items-center gap-3">
                        {statusIcon(check.status)}
                        <div>
                          <p className="text-sm font-medium">{language === 'ar' ? check.description_ar : check.description}</p>
                          <p className="text-xs text-slate-400">{language === 'ar' ? `${check.total_checked} فحص` : `${check.total_checked} checked`}</p>
                        </div>
                      </div>
                      <Badge variant={check.status === 'pass' ? 'outline' : 'destructive'} className="text-xs">
                        {check.status.toUpperCase()}
                      </Badge>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          <Button onClick={fetchIntegrity} variant="outline" size="sm">
            {language === 'ar' ? 'إعادة التحقق' : 'Re-validate'}
          </Button>
        </div>
      )}

      {/* Audit Trail Tab */}
      {activeTab === 'audit' && !loading && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText size={20} className="text-indigo-500" />
              {language === 'ar' ? 'سجل تدقيق GRC (مع القيم السابقة/الجديدة)' : 'GRC Audit Trail (with prev/new values)'}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {auditTrail.length === 0 ? (
              <div className="text-center py-8 text-slate-400">
                <FileText size={32} className="mx-auto mb-2" />
                <p>{language === 'ar' ? 'لا توجد سجلات تدقيق GRC بعد' : 'No GRC audit trail entries yet'}</p>
                <p className="text-xs">{language === 'ar' ? 'ستظهر الإدخالات عند إنشاء/تحديث/حذف كيانات GRC' : 'Entries appear when GRC entities are created/updated/deleted'}</p>
              </div>
            ) : (
              <div className="space-y-3 max-h-[600px] overflow-y-auto">
                {auditTrail.map(entry => (
                  <div key={entry.id} className="border rounded-lg p-3">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-xs">{entry.action}</Badge>
                        <Badge className="text-xs bg-slate-100 text-slate-700">{entry.resource_type}</Badge>
                      </div>
                      <span className="text-xs text-slate-400">
                        {entry.created_at ? new Date(entry.created_at).toLocaleString() : ''}
                      </span>
                    </div>
                    {entry.details?.summary && (
                      <p className="text-sm text-slate-700 mb-1">
                        {language === 'ar' && entry.details.summary_ar ? entry.details.summary_ar : entry.details.summary}
                      </p>
                    )}
                    {entry.details?.changed_fields && entry.details.changed_fields.length > 0 && (
                      <div className="flex gap-1 flex-wrap">
                        <span className="text-xs text-slate-400">{language === 'ar' ? 'الحقول المتغيرة:' : 'Changed:'}</span>
                        {entry.details.changed_fields.map(f => (
                          <Badge key={f} variant="outline" className="text-xs">{f}</Badge>
                        ))}
                      </div>
                    )}
                    <p className="text-xs text-slate-300 mt-1 font-mono truncate">{entry.entry_hash}</p>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* RBAC Tab */}
      {activeTab === 'rbac' && !loading && rbac && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Lock size={20} className="text-purple-500" />
              {language === 'ar' ? 'الأدوار والصلاحيات' : 'Role-Based Access Control'}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="mb-4 p-3 bg-slate-50 rounded-lg">
              <p className="text-sm"><strong>{language === 'ar' ? 'البريد الإلكتروني:' : 'Email:'}</strong> {rbac.email}</p>
              <p className="text-sm"><strong>{language === 'ar' ? 'الدور:' : 'Role:'}</strong> <Badge>{rbac.role}</Badge></p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-start p-2">{language === 'ar' ? 'الوحدة' : 'Module'}</th>
                    <th className="text-center p-2">{language === 'ar' ? 'قراءة' : 'Read'}</th>
                    <th className="text-center p-2">{language === 'ar' ? 'كتابة' : 'Write'}</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(rbac.permissions).map(([module, perms]) => (
                    <tr key={module} className="border-b">
                      <td className="p-2 capitalize">{module.replace(/_/g, ' ')}</td>
                      <td className="text-center p-2">
                        {perms.read ? <CheckCircle size={16} className="mx-auto text-green-500" /> : <AlertTriangle size={16} className="mx-auto text-red-400" />}
                      </td>
                      <td className="text-center p-2">
                        {perms.write ? <CheckCircle size={16} className="mx-auto text-green-500" /> : <Lock size={16} className="mx-auto text-slate-300" />}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Exports Tab */}
      {activeTab === 'exports' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">{language === 'ar' ? 'تصدير CSV' : 'CSV Exports'}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {[
                { type: 'risks', label: language === 'ar' ? 'سجل المخاطر' : 'Risk Register', file: 'risk_register.csv' },
                { type: 'issues', label: language === 'ar' ? 'المشاكل' : 'Issues', file: 'issues.csv' },
                { type: 'actions', label: language === 'ar' ? 'الإجراءات' : 'Actions', file: 'actions.csv' },
                { type: 'findings', label: language === 'ar' ? 'نتائج التدقيق' : 'Audit Findings', file: 'audit_findings.csv' },
              ].map(exp => (
                <Button
                  key={exp.type}
                  variant="outline"
                  className="w-full justify-start gap-2"
                  onClick={() => downloadCSV(exp.type, exp.file)}
                >
                  <Download size={16} />
                  {exp.label}
                </Button>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">{language === 'ar' ? 'التقارير' : 'Reports'}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <Button
                variant="outline"
                className="w-full justify-start gap-2"
                onClick={downloadExecutiveReport}
              >
                <FileText size={16} />
                {language === 'ar' ? 'تقرير تنفيذي (JSON)' : 'Executive Report (JSON)'}
              </Button>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
