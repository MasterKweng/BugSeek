import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { message } from 'antd'
import type { Project, Version } from '../types'
import * as projectService from '../services/project'
import * as versionService from '../services/version'

interface ProjectState {
  currentProject: Project | null
  currentVersion: Version | null
  projects: Project[]
  versions: Version[]
  loading: boolean
  
  // Actions
  setCurrentProject: (project: Project) => void
  setCurrentVersion: (version: Version | null) => void
  clearCurrentContext: () => void
  fetchProjects: () => Promise<void>
  fetchVersions: (projectId: number) => Promise<void>
  initializeFromStorage: () => void
}

export const useProjectStore = create<ProjectState>()(
  persist(
    (set, get) => ({
      currentProject: null,
      currentVersion: null,
      projects: [],
      versions: [],
      loading: false,

      setCurrentProject: (project) => {
        if (!project || typeof project.id !== 'number' || isNaN(project.id)) {
          console.error('无效的项目 ID:', project?.id)
          message.error('无效的项目信息')
          return
        }
        set({ currentProject: project })
        // 切换项目时，清空当前版本
        set({ currentVersion: null })
        // 自动获取该项目的版本列表
        get().fetchVersions(project.id)
      },

      setCurrentVersion: (version) => {
        if (version === null) {
          set({ currentVersion: null })
          return
        }
        if (typeof version.id !== 'number' || isNaN(version.id)) {
          console.error('无效的版本 ID:', version.id)
          message.error('无效的版本信息')
          return
        }
        set({ currentVersion: version })
      },

      clearCurrentContext: () => {
        set({ currentProject: null, currentVersion: null })
      },

      fetchProjects: async () => {
        set({ loading: true })
        try {
          const response = await projectService.getProjects({ page: 1, page_size: 100 })
          const nextProjects = response.data?.items || []
          const currentProjectId = get().currentProject?.id
          const refreshedCurrentProject = nextProjects.find((item) => item.id === currentProjectId) || null
          set({
            projects: nextProjects,
            currentProject: refreshedCurrentProject ?? get().currentProject,
          })
        } catch (error) {
          console.error('获取项目列表失败:', error)
          message.error('获取项目列表失败，请稍后重试')
        } finally {
          set({ loading: false })
        }
      },

      fetchVersions: async (projectId: number) => {
        if (typeof projectId !== 'number' || isNaN(projectId)) {
          console.error('无效的 project_id:', projectId)
          message.error('无效的项目 ID')
          return
        }

        set({ loading: true })
        try {
          const response = await versionService.getVersions(projectId, { page: 1, page_size: 100 })
          const nextVersions = response.data?.items || []
          const currentVersionId = get().currentVersion?.id
          const refreshedCurrentVersion = nextVersions.find((item) => item.id === currentVersionId) || null
          set({
            versions: nextVersions,
            currentVersion: refreshedCurrentVersion ?? get().currentVersion,
          })

          // 如果有版本列表但未选择当前版本，自动选择最新的版本
          const { currentVersion, versions } = get()
          if (!currentVersion && versions?.length > 0) {
            // 选择最新版本（按创建时间倒序的第一个）
            set({ currentVersion: versions[0] })
          }
        } catch (error) {
          console.error('获取版本列表失败:', error)
          message.error('获取版本列表失败，请稍后重试')
        } finally {
          set({ loading: false })
        }
      },

      initializeFromStorage: () => {
        const { currentProject } = get()
        // 验证从 localStorage 读取的数据
        if (currentProject && typeof currentProject.id === 'number' && !isNaN(currentProject.id)) {
          get().fetchVersions(currentProject.id)
        } else if (currentProject) {
          // 如果 project 存在但 id 无效，清空当前项目
          console.error('从存储读取的项目数据无效，已清空')
          set({ currentProject: null, currentVersion: null })
        }
      },
    }),
    {
      name: 'project-storage',
      partialize: (state) => ({
        currentProject: state.currentProject,
        currentVersion: state.currentVersion,
      }),
    }
  )
)
