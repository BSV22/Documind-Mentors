/**
 * Utility for making authenticated API requests with HttpOnly cookies
 */

export const apiCall = async (endpoint, options = {}) => {
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  try {
    const response = await fetch(endpoint, {
      ...options,
      headers,
      credentials: 'same-origin',
    });

    if (response.status === 401) {
      throw new Error('Unauthorized - please log in again');
    }

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `API call failed: ${response.status}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('API call error:', error);
    throw error;
  }
};

/**
 * POST request with cookie authentication
 */
export const apiPost = (endpoint, body, options = {}) => {
  return apiCall(endpoint, {
    ...options,
    method: 'POST',
    body: JSON.stringify(body),
  });
};

/**
 * GET request with cookie authentication
 */
export const apiGet = (endpoint, options = {}) => {
  return apiCall(endpoint, {
    ...options,
    method: 'GET',
  });
};

/**
 * PUT request with cookie authentication
 */
export const apiPut = (endpoint, body, options = {}) => {
  return apiCall(endpoint, {
    ...options,
    method: 'PUT',
    body: JSON.stringify(body),
  });
};

/**
 * DELETE request with cookie authentication
 */
export const apiDelete = (endpoint, options = {}) => {
  return apiCall(endpoint, {
    ...options,
    method: 'DELETE',
  });
};
