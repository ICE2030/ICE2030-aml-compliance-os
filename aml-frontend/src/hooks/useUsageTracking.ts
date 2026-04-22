import { useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import api from '@/services/api';

/**
 * Fires a `navigate` usage event whenever the route changes.
 *
 * Silent — never throws into the UI if the backend is unavailable.
 */
export function useUsageTracking() {
  const location = useLocation();
  const lastPath = useRef<string | null>(null);

  useEffect(() => {
    const path = location.pathname;
    if (!path || path === lastPath.current) return;
    lastPath.current = path;

    // Don't track navigation while logged out.
    if (!localStorage.getItem('token')) return;
    if (path === '/login') return;

    api
      .post('/api/usage/events', {
        event_type: 'navigate',
        path,
      })
      .catch(() => {
        // Telemetry is fire-and-forget.
      });
  }, [location.pathname]);
}

/**
 * Record a discrete user action (create / update / delete / export / etc.).
 *
 * Used by forms and list views to leave a light trail for the admin usage
 * dashboard without hooking into every route handler.
 */
export function trackUsage(
  event_type: 'create' | 'update' | 'delete' | 'export' | 'demo_flow_view' | 'seed_load' | 'login' | 'logout',
  params: {
    resource_type?: string;
    resource_id?: string;
    path?: string;
    metadata?: Record<string, unknown>;
  } = {},
) {
  if (!localStorage.getItem('token') && event_type !== 'login') return;
  api
    .post('/api/usage/events', { event_type, ...params })
    .catch(() => {
      // Intentional no-op.
    });
}
