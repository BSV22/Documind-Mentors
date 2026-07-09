import { createContext, useState, useEffect, useCallback, useContext } from 'react';
import { apiGet, apiPost } from '../utils/api';

export const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Initialize from session check on mount
  useEffect(() => {
    const checkSession = async () => {
      try {
        const data = await apiGet('/api/auth/me');
        if (data && data.user) {
          setUser(data.user);
        }
      } catch (err) {
        console.log('No active session found.');
      } finally {
        setLoading(false);
      }
    };
    checkSession();
  }, []);

  const login = useCallback((token, userData = null) => {
    // userData contains the user details returned from backend signin/signup/google endpoints
    setUser(userData);
    setError(null);
    return true;
  }, []);

  const logout = useCallback(async () => {
    try {
      await apiPost('/api/auth/signout');
    } catch (err) {
      console.error('Signout request failed:', err);
    }
    setUser(null);
  }, []);

  const signup = useCallback((token, userData) => {
    return login(null, userData);
  }, [login]);

  const value = {
    user,
    loading,
    error,
    login,
    logout,
    signup,
    isAuthenticated: !!user,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};
