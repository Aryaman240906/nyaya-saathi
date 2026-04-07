const API_BASE = process.env.NEXT_PUBLIC_API_URL ;

// ── Token Management ───────────────────────────────────────────────
let _accessToken = null;
let _refreshToken = null;

function _loadTokens() {
  if (typeof window !== "undefined") {
    _accessToken = localStorage.getItem("ns_access_token");
    _refreshToken = localStorage.getItem("ns_refresh_token");
  }
}

function _saveTokens(access, refresh) {
  _accessToken = access;
  _refreshToken = refresh;
  if (typeof window !== "undefined") {
    localStorage.setItem("ns_access_token", access);
    localStorage.setItem("ns_refresh_token", refresh);
  }
}

function _clearTokens() {
  _accessToken = null;
  _refreshToken = null;
  if (typeof window !== "undefined") {
    localStorage.removeItem("ns_access_token");
    localStorage.removeItem("ns_refresh_token");
    localStorage.removeItem("ns_user");
  }
}

function _authHeaders() {
  _loadTokens();
  if (_accessToken) {
    return { Authorization: `Bearer ${_accessToken}` };
  }
  return {};
}

async function _fetchWithAuth(url, options = {}) {
  _loadTokens();
  const headers = { ...options.headers, ..._authHeaders() };
  let res = await fetch(url, { ...options, headers });

  // If 401, try refresh
  if (res.status === 401 && _refreshToken) {
    const refreshed = await refreshAuth();
    if (refreshed) {
      const retryHeaders = { ...options.headers, ..._authHeaders() };
      res = await fetch(url, { ...options, headers: retryHeaders });
    }
  }

  return res;
}

// ── Auth ───────────────────────────────────────────────────────────
export async function signup(email, password, name) {
  const res = await fetch(`${API_BASE}/api/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, name }),
  });

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `Signup failed: ${res.status}`);
  }

  const data = await res.json();
  _saveTokens(data.access_token, data.refresh_token);
  if (typeof window !== "undefined") {
    localStorage.setItem("ns_user", JSON.stringify(data.user));
  }
  return data;
}

export async function login(email, password) {
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `Login failed: ${res.status}`);
  }

  const data = await res.json();
  _saveTokens(data.access_token, data.refresh_token);
  if (typeof window !== "undefined") {
    localStorage.setItem("ns_user", JSON.stringify(data.user));
  }
  return data;
}

export async function refreshAuth() {
  if (!_refreshToken) return false;

  try {
    const res = await fetch(`${API_BASE}/api/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: _refreshToken }),
    });

    if (!res.ok) {
      _clearTokens();
      return false;
    }

    const data = await res.json();
    _saveTokens(data.access_token, data.refresh_token);
    if (typeof window !== "undefined") {
      localStorage.setItem("ns_user", JSON.stringify(data.user));
    }
    return true;
  } catch {
    _clearTokens();
    return false;
  }
}

export async function logout() {
  try {
    await _fetchWithAuth(`${API_BASE}/api/auth/logout`, { method: "POST" });
  } catch {
    // ignore errors during logout
  }
  _clearTokens();
}

export async function getMe() {
  const res = await _fetchWithAuth(`${API_BASE}/api/auth/me`);
  if (!res.ok) return null;
  return res.json();
}

export function getStoredUser() {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem("ns_user");
  return raw ? JSON.parse(raw) : null;
}

export function isLoggedIn() {
  _loadTokens();
  return !!_accessToken;
}

// ── Chat ───────────────────────────────────────────────────────────
export async function sendChatMessage(message, sessionId = null, language = "en", mode = "debate") {
  const response = await _fetchWithAuth(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      session_id: sessionId,
      language,
      mode,
    }),
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response.body.getReader();
}

export async function* parseSSEStream(reader) {
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed.startsWith("data: ")) {
        try {
          const data = JSON.parse(trimmed.slice(6));
          yield data;
        } catch (e) {
          console.warn("SSE parse error:", e);
        }
      }
    }
  }
}

// ── Sessions / History ─────────────────────────────────────────────
export async function getSessions(page = 1, limit = 20) {
  const res = await _fetchWithAuth(`${API_BASE}/api/sessions?page=${page}&limit=${limit}`);
  if (!res.ok) throw new Error("Failed to fetch sessions");
  return res.json();
}

export async function getSession(sessionId) {
  const res = await _fetchWithAuth(`${API_BASE}/api/sessions/${sessionId}`);
  if (!res.ok) throw new Error("Failed to fetch session");
  return res.json();
}

export async function deleteSession(sessionId) {
  const res = await _fetchWithAuth(`${API_BASE}/api/sessions/${sessionId}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("Failed to delete session");
  return res.json();
}

export async function searchHistory(query) {
  const res = await _fetchWithAuth(
    `${API_BASE}/api/sessions/search?q=${encodeURIComponent(query)}`
  );
  if (!res.ok) throw new Error("Failed to search history");
  return res.json();
}

export async function exportSession(sessionId) {
  const res = await _fetchWithAuth(`${API_BASE}/api/sessions/${sessionId}/export`);
  if (!res.ok) throw new Error("Failed to export session");
  return res.json();
}

// ── Bookmarks ──────────────────────────────────────────────────────
export async function addBookmark(sectionId, act = "", sectionNumber = "", title = "", note = "") {
  const res = await _fetchWithAuth(`${API_BASE}/api/bookmarks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      section_id: sectionId,
      act,
      section_number: sectionNumber,
      title,
      note,
    }),
  });
  if (!res.ok) throw new Error("Failed to add bookmark");
  return res.json();
}

export async function getBookmarks() {
  const res = await _fetchWithAuth(`${API_BASE}/api/bookmarks`);
  if (!res.ok) throw new Error("Failed to fetch bookmarks");
  return res.json();
}

export async function deleteBookmark(bookmarkId) {
  const res = await _fetchWithAuth(`${API_BASE}/api/bookmarks/${bookmarkId}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("Failed to delete bookmark");
  return res.json();
}

// ── Procedures ─────────────────────────────────────────────────────
export async function getProcedures() {
  const res = await fetch(`${API_BASE}/api/procedures`);
  if (!res.ok) throw new Error("Failed to fetch procedures");
  return res.json();
}

export async function getProcedure(id) {
  const res = await fetch(`${API_BASE}/api/procedures/${id}`);
  if (!res.ok) throw new Error("Failed to fetch procedure");
  return res.json();
}

// ── Rights ─────────────────────────────────────────────────────────
export async function getRightsCategories() {
  const res = await fetch(`${API_BASE}/api/rights/categories`);
  if (!res.ok) throw new Error("Failed to fetch categories");
  return res.json();
}

export async function getRightsByCategory(categoryId) {
  const res = await fetch(`${API_BASE}/api/rights/category/${categoryId}`);
  if (!res.ok) throw new Error("Failed to fetch rights");
  return res.json();
}

export async function searchRights(query) {
  const res = await fetch(`${API_BASE}/api/rights/search?q=${encodeURIComponent(query)}`);
  if (!res.ok) throw new Error("Failed to search rights");
  return res.json();
}

// ── Pipeline / Stats ───────────────────────────────────────────────
export async function getHealth() {
  try {
    const res = await fetch(`${API_BASE}/api/health`);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function getPipelineStats() {
  try {
    const res = await fetch(`${API_BASE}/api/pipeline/stats`);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function getPipelineNodes() {
  try {
    const res = await fetch(`${API_BASE}/api/pipeline/nodes`);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function getStats() {
  try {
    const res = await fetch(`${API_BASE}/api/stats`);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}
