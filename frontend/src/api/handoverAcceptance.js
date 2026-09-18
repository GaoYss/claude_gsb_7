import { createResourceApi } from './client'
import http from './client'

export const handoverAcceptanceApi = {
  ...createResourceApi('handover-acceptances'),
  summary: (params) => http.get('/handover-acceptances/summary', { params }),
  accept: (id, payload) => http.post(`/handover-acceptances/${id}/accept`, payload),
  complete: (id, payload) => http.post(`/handover-acceptances/${id}/complete`, payload || {}),
  createDefect: (id, payload) => http.post(`/handover-acceptances/${id}/defects`, payload),
  updateDefect: (id, defectId, payload) =>
    http.put(`/handover-acceptances/${id}/defects/${defectId}`, payload),
  removeDefect: (id, defectId) => http.delete(`/handover-acceptances/${id}/defects/${defectId}`),
  createRevisit: (id, payload) => http.post(`/handover-acceptances/${id}/revisits`, payload),
  updateRevisit: (id, revisitId, payload) =>
    http.put(`/handover-acceptances/${id}/revisits/${revisitId}`, payload),
  removeRevisit: (id, revisitId) => http.delete(`/handover-acceptances/${id}/revisits/${revisitId}`),
}
