import { create } from 'zustand'

import type { ScenarioLifecycleStatus, ScenarioRuntimeType } from '../types/scenario'

interface ScenarioFilters {
  search?: string
  lifecycle_status?: ScenarioLifecycleStatus | 'all'
  runtime_type?: ScenarioRuntimeType | 'all'
  template_category?: string
}

interface ScenarioStore {
  currentScenarioId: number | null
  currentRevisionId: number | null
  currentRunId: number | null
  selectedEnvironmentId: number | null
  filters: ScenarioFilters
  setCurrentScenarioId: (scenarioId: number | null) => void
  setCurrentRevisionId: (revisionId: number | null) => void
  setCurrentRunId: (runId: number | null) => void
  setSelectedEnvironmentId: (environmentId: number | null) => void
  setFilters: (filters: Partial<ScenarioFilters>) => void
  resetFilters: () => void
  reset: () => void
}

const initialFilters: ScenarioFilters = {
  search: '',
  lifecycle_status: 'all',
  runtime_type: 'all',
  template_category: '',
}

export const useScenarioStore = create<ScenarioStore>((set) => ({
  currentScenarioId: null,
  currentRevisionId: null,
  currentRunId: null,
  selectedEnvironmentId: null,
  filters: initialFilters,
  setCurrentScenarioId: (currentScenarioId) => set({ currentScenarioId }),
  setCurrentRevisionId: (currentRevisionId) => set({ currentRevisionId }),
  setCurrentRunId: (currentRunId) => set({ currentRunId }),
  setSelectedEnvironmentId: (selectedEnvironmentId) => set({ selectedEnvironmentId }),
  setFilters: (filters) =>
    set((state) => ({
      filters: {
        ...state.filters,
        ...filters,
      },
    })),
  resetFilters: () => set({ filters: initialFilters }),
  reset: () =>
    set({
      currentScenarioId: null,
      currentRevisionId: null,
      currentRunId: null,
      selectedEnvironmentId: null,
      filters: initialFilters,
    }),
}))
