import { createContext, useState, useEffect, useCallback, useContext } from 'react';
import { jwtDecode } from 'jwt-decode';

export const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Initialize from localStorage on mount
  useEffect(() => {
    const storedToken = localStorage.getItem('authToken');
    if (storedToken) {
      try {
        const decoded = jwtDecode(storedToken);
        // Check if token is expired
        if (decoded.exp * 1000 > Date.now()) {
          setToken(storedToken);
          setUser(decoded);
        } else {
          // Token expired, clear it
          localStorage.removeItem('authToken');
        }
      } catch (err) {
        console.error('Failed to decode token:', err);
        localStorage.removeItem('authToken');
      }
    }
    setLoading(false);
  }, []);

  const login = useCallback((token, userData = null) => {
    try {
      const decoded = userData || jwtDecode(token);
      setToken(token);
      setUser(decoded);
      localStorage.setItem('authToken', token);
      setError(null);
      return true;
    } catch (err) {
      console.error('Login failed:', err);
      setError('Invalid token');
      return false;
    }
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    localStorage.removeItem('authToken');
  }, []);

  const signup = useCallback((token, userData) => {
    return login(token, userData);
  }, [login]);

  const value = {
    user,
    token,
    loading,
    error,
    login,
    logout,
    signup,
    isAuthenticated: !!token,
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
