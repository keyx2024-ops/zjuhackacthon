import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  timeout: 120000,
});

api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const message = error.response?.data?.detail || error.message;
    console.error('API error:', message);
    return Promise.reject(new Error(message));
  }
);

export const textbookApi = {
  upload(file) {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/textbooks/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  list() {
    return api.get('/textbooks');
  },
  get(id) {
    return api.get(`/textbooks/${id}`);
  },
  delete(id) {
    return api.delete(`/textbooks/${id}`);
  },
};

export const graphApi = {
  build(textbookId, options = {}) {
    const params = options.force ? '?force=true' : '';
    return api.post(`/graphs/build/${textbookId}${params}`);
  },
  getBuildProgress(jobId) {
    return api.get(`/graphs/progress/${jobId}`);
  },
  getByTextbook(textbookId) {
    return api.get(`/graphs/textbook/${textbookId}`);
  },
  get(graphId) {
    return api.get(`/graphs/${graphId}`);
  },
};

export const integrationApi = {
  start(textbookIds, targetRatio = null) {
    const payload = { textbook_ids: textbookIds };
    if (typeof targetRatio === 'number' && targetRatio > 0) {
      payload.target_ratio = targetRatio;
    }
    return api.post('/integration/start', payload);
  },
  getProgress(jobId) {
    return api.get(`/integration/progress/${jobId}`);
  },
  getLatest() {
    return api.get('/integration/latest');
  },
  getDecisions(resultId) {
    return api.get(`/integration/${resultId}/decisions`);
  },
};

export const ragApi = {
  buildIndex(textbookIds) {
    return api.post('/rag/index', { textbook_ids: textbookIds });
  },
  query(query, options = {}) {
    return api.post('/rag/query', {
      query,
      top_k: options.topK || 5,
      use_rerank: options.useRerank !== false,
      use_hybrid_search: options.useHybridSearch !== false,
      textbook_ids: options.textbookIds,
    });
  },
  status() {
    return api.get('/rag/status');
  },
};

export const dialogueApi = {
  chat(message, sessionId = null) {
    return api.post('/dialogue/chat', {
      message,
      session_id: sessionId,
    });
  },
  getSession(sessionId) {
    return api.get(`/dialogue/session/${sessionId}`);
  },
};

export default api;
