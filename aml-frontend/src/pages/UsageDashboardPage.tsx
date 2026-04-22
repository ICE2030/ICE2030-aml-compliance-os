import { useEffect, useState } from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Activity, Eye, Edit3, Trash2, PlusCircle, Compass, Users, FileDown } from 'lucide-react';
import api from '@/services/api';

interface Summary {
  window_days: number;
  since: string;
  total_events: number;
  active_users: number;
  by_event_type: Record<string, number>;
  by_resource_type: Record<string, number>;
  top_paths: { path: string; count: number }[];
}

interface UsageEvent {
  id: string;
  event_type: string;
  resource_type: string | null;
  resource_id: string | null;
  path: string | null;
  metadata: Record<string, unknown>;
  user_id: string | null;
  created_at: string | null;
}

const EVENT_ICON: Record<string, typeof Activity> = {
  create: PlusCircle,
  update: Edit3,
  delete: Trash2,
  navigate: Eye,
  demo_flow_view: Compass,
  export: FileDown,
  seed_load: Activity,
  login: Users,
  logout: Users,
};

export default function UsageDashboardPage() {
  const { language } = useLanguage();
  const isAr = language === 'ar';
  const [summary, setSummary] = useState<Summary | null>(null);
  const [events, setEvents] = useState<UsageEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(7);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.get(`/api/usage/summary?days=${days}`).then((r) => r.data as Summary),
      api.get('/api/usage/events?limit=50').then((r) => r.data.items as UsageEvent[]),
    ])
      .then(([s, e]) => {
        setSummary(s);
        setEvents(e);
      })
      .finally(() => setLoading(false));
  }, [days]);

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <Activity size={22} className="text-blue-600" />
            {isAr ? 'استخدام النظام' : 'System Usage'}
          </h1>
          <p className="text-slate-500 mt-1 max-w-2xl text-sm">
            {isAr
              ? 'نظرة خفيفة على نشاط المستخدمين: الإنشاء، التحديث، الحذف، والتنقل. ليست منصة تحليلات كاملة — فقط إشارات أساسية للقابلية للاستخدام.'
              : 'Lightweight view of user activity: creates, updates, deletes, and navigation. Not a full analytics platform — just basic usability signals.'}
          </p>
        </div>
        <select
          value={days}
          onChange={(e) => setDays(parseInt(e.target.value, 10))}
          className="border rounded-md px-3 py-2 text-sm"
        >
          <option value="1">{isAr ? 'آخر 24 ساعة' : 'Last 24 hours'}</option>
          <option value="7">{isAr ? 'آخر 7 أيام' : 'Last 7 days'}</option>
          <option value="30">{isAr ? 'آخر 30 يوماً' : 'Last 30 days'}</option>
          <option value="90">{isAr ? 'آخر 90 يوماً' : 'Last 90 days'}</option>
        </select>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-32">
          <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : (
        <>
          {summary && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <Card>
                <CardContent className="pt-4 text-center">
                  <p className="text-sm text-slate-500">{isAr ? 'إجمالي الأحداث' : 'Total Events'}</p>
                  <p className="text-2xl font-bold">{summary.total_events}</p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-4 text-center">
                  <p className="text-sm text-slate-500">{isAr ? 'المستخدمون النشطون' : 'Active Users'}</p>
                  <p className="text-2xl font-bold">{summary.active_users}</p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-4 text-center">
                  <p className="text-sm text-slate-500">{isAr ? 'أحداث الإنشاء' : 'Creates'}</p>
                  <p className="text-2xl font-bold text-green-700">
                    {summary.by_event_type.create || 0}
                  </p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-4 text-center">
                  <p className="text-sm text-slate-500">{isAr ? 'أحداث التنقل' : 'Navigations'}</p>
                  <p className="text-2xl font-bold">{summary.by_event_type.navigate || 0}</p>
                </CardContent>
              </Card>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-semibold">
                  {isAr ? 'النشاط حسب النوع' : 'Activity by Type'}
                </CardTitle>
              </CardHeader>
              <CardContent>
                {summary && Object.keys(summary.by_event_type).length === 0 ? (
                  <p className="text-sm text-slate-400">{isAr ? 'لا يوجد نشاط بعد.' : 'No activity yet.'}</p>
                ) : (
                  <ul className="space-y-2 text-sm">
                    {summary &&
                      Object.entries(summary.by_event_type)
                        .sort((a, b) => b[1] - a[1])
                        .map(([type, count]) => {
                          const Icon = EVENT_ICON[type] || Activity;
                          return (
                            <li key={type} className="flex items-center justify-between">
                              <span className="flex items-center gap-2 text-slate-700">
                                <Icon size={14} />
                                {type}
                              </span>
                              <span className="font-semibold">{count}</span>
                            </li>
                          );
                        })}
                  </ul>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-semibold">
                  {isAr ? 'أكثر الصفحات زيارة' : 'Most Visited Pages'}
                </CardTitle>
              </CardHeader>
              <CardContent>
                {summary && summary.top_paths.length === 0 ? (
                  <p className="text-sm text-slate-400">
                    {isAr ? 'لا توجد بيانات تنقل بعد.' : 'No navigation data yet.'}
                  </p>
                ) : (
                  <ul className="space-y-2 text-sm">
                    {summary &&
                      summary.top_paths.map((p) => (
                        <li key={p.path} className="flex items-center justify-between">
                          <code className="text-slate-700 text-xs truncate max-w-[220px]">{p.path}</code>
                          <span className="font-semibold">{p.count}</span>
                        </li>
                      ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-semibold">
                {isAr ? 'أحدث الأحداث' : 'Latest Events'}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {events.length === 0 ? (
                <p className="text-sm text-slate-400">
                  {isAr ? 'لا توجد أحداث.' : 'No events recorded.'}
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="text-slate-500 text-start border-b">
                        <th className="py-2 text-start">{isAr ? 'الوقت' : 'Time'}</th>
                        <th className="py-2 text-start">{isAr ? 'النوع' : 'Type'}</th>
                        <th className="py-2 text-start">{isAr ? 'المورد' : 'Resource'}</th>
                        <th className="py-2 text-start">{isAr ? 'المسار' : 'Path'}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {events.map((ev) => (
                        <tr key={ev.id} className="border-b last:border-b-0">
                          <td className="py-1.5 text-slate-600 whitespace-nowrap">
                            {ev.created_at ? new Date(ev.created_at).toLocaleString() : '—'}
                          </td>
                          <td className="py-1.5 font-medium">{ev.event_type}</td>
                          <td className="py-1.5 text-slate-600">
                            {ev.resource_type || '—'}
                          </td>
                          <td className="py-1.5 text-slate-500">
                            <code className="text-xs">{ev.path || '—'}</code>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
