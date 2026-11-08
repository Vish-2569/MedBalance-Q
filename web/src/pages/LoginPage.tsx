import { useState, useEffect } from 'react';
import { Shield, LogIn, Loader2 } from 'lucide-react';
import { login, fetchUsers } from '@/lib/auth';

interface Props {
  onLogin: () => void;
}

export default function LoginPage({ onLogin }: Props) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [users, setUsers] = useState<{ username: string; role: string; name: string }[]>([]);

  useEffect(() => {
    fetchUsers().then(setUsers);
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(username, password);
      onLogin();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setLoading(false);
    }
  }

  function quickLogin(u: string, p: string) {
    setUsername(u);
    setPassword(p);
    setError('');
    setLoading(true);
    login(u, p)
      .then(() => onLogin())
      .catch(err => setError(err instanceof Error ? err.message : 'Login failed'))
      .finally(() => setLoading(false));
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-teal-50 to-slate-100 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-teal-600 text-white mb-4">
            <Shield className="w-8 h-8" />
          </div>
          <h1 className="text-2xl font-bold text-slate-800">MedBalance-Q</h1>
          <p className="text-slate-500 text-sm mt-1">District Medicine Redistribution System</p>
        </div>

        <div className="bg-white rounded-xl shadow-lg p-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="username" className="block text-sm font-medium text-slate-700 mb-1">
                Username
              </label>
              <input
                id="username"
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:border-teal-400 focus:ring-1 focus:ring-teal-400"
                autoComplete="username"
                required
              />
            </div>
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-slate-700 mb-1">
                Password
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:border-teal-400 focus:ring-1 focus:ring-teal-400"
                autoComplete="current-password"
                required
              />
            </div>

            {error && (
              <div className="text-red-600 text-sm bg-red-50 rounded-lg px-3 py-2">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !username || !password}
              className="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-teal-600 text-white font-medium text-sm hover:bg-teal-700 disabled:opacity-50 transition-colors"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <LogIn className="w-4 h-4" />}
              Sign In
            </button>
          </form>

          {users.length > 0 && (
            <div className="mt-6 pt-4 border-t border-slate-200">
              <p className="text-xs text-slate-500 mb-3">Quick login (demo accounts):</p>
              <div className="grid grid-cols-2 gap-2">
                {users.map(u => (
                  <button
                    key={u.username}
                    onClick={() => quickLogin(u.username, `${u.username}123`)}
                    disabled={loading}
                    className="text-left px-3 py-2 rounded-lg border border-slate-200 hover:bg-teal-50 hover:border-teal-200 transition-colors disabled:opacity-50"
                  >
                    <div className="text-sm font-medium text-slate-700">{u.name}</div>
                    <div className="text-[11px] text-slate-400">{u.role}</div>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        <p className="text-center text-[11px] text-slate-400 mt-4">
          Simulated district data — not connected to live systems
        </p>
      </div>
    </div>
  );
}
