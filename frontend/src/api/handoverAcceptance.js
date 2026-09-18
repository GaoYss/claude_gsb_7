import { createResourceApi } from './client'
import http from './client'

export const handoverAcceptanceApi = {
  ...createResourceApi('handover-acceptances'),
  accept: (id, payload) => http.post(`/handover-acceptances/${id}/accept`, payload),
  close: (id) => http.post(`/handover-acceptances/${id}/close`),
  addDefect: (id, payload) => http.post(`/handover-acceptances/${id}/defects`, payload),
  completeDefect: (id, defectId, payload) =>
    http.patch(`/handover-acceptances/${id}/defects/${defectId}/complete`, payload),
  removeDefect: (id, defectId) => http.delete(`/handover-acceptances/${id}/defects/${defectId}`),
  addFollowUp: (id, payload) => http.post(`/handover-acceptances/${id}/follow-ups`, payload),
  updateFollowUp: (id, followUpId, payload) =>
    http.put(`/handover-acceptances/${id}/follow-ups/${followUpId}`, payload),
}
