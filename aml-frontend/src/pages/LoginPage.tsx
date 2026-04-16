import { useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useLanguage } from '@/contexts/LanguageContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Shield, Globe } from 'lucide-react';

export default function LoginPage() {
  const { login } = useAuth();
  const { t, language, setLanguage } = useLanguage();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(email, password);
    } catch {
      setError(t('login.error'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-900 to-slate-900 flex items-center justify-center p-4" dir={language === 'ar' ? 'rtl' : 'ltr'}>
      <div className="absolute top-4 right-4">
        <Button variant="ghost" size="sm" onClick={() => setLanguage(language === 'en' ? 'ar' : 'en')} className="text-white hover:bg-white/10">
          <Globe size={16} className="me-2" />
          {language === 'en' ? 'العربية' : 'English'}
        </Button>
      </div>

      <Card className="w-full max-w-md">
        <CardHeader className="text-center space-y-4">
          <div className="mx-auto w-16 h-16 bg-blue-600 rounded-2xl flex items-center justify-center">
            <Shield className="text-white" size={32} />
          </div>
          <div>
            <CardTitle className="text-2xl">{t('app.title')}</CardTitle>
            <p className="text-sm text-slate-500 mt-1">{t('app.subtitle')}</p>
          </div>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
                {error}
              </div>
            )}
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700">{t('login.email')}</label>
              <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="admin@aml-os.sa" required />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700">{t('login.password')}</label>
              <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
            </div>
            <Button type="submit" className="w-full bg-blue-600 hover:bg-blue-700" disabled={loading}>
              {loading ? t('common.loading') : t('login.submit')}
            </Button>
            <div className="text-center text-xs text-slate-400 mt-4">
              <p>Demo: admin@aml-os.sa / admin123</p>
              <p>Officer: officer@aml-os.sa / officer123</p>
              <p>Analyst: analyst@aml-os.sa / analyst123</p>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
