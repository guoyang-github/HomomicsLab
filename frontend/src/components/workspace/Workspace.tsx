import { useState } from 'react'
import { FlowCanvas } from './FlowCanvas'
import { DetailPanel } from './DetailPanel'
import { ReportPanel } from '@/components/reports/ReportPanel'
import { SkillSearch } from '@/components/skills/SkillSearch'
import { SkillGenerator } from '@/components/skills/SkillGenerator'

type WorkspaceTab = 'workflow' | 'reports' | 'skills' | 'generate'

export function Workspace() {
  const [activeTab, setActiveTab] = useState<WorkspaceTab>('workflow')

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-2">
        <h2 className="text-sm font-semibold text-slate-800">工作空间</h2>
        <div className="flex rounded-lg bg-slate-100 p-0.5">
          <button
            onClick={() => setActiveTab('workflow')}
            className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
              activeTab === 'workflow'
                ? 'bg-white text-slate-800 shadow-sm'
                : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            Workflow
          </button>
          <button
            onClick={() => setActiveTab('reports')}
            className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
              activeTab === 'reports'
                ? 'bg-white text-slate-800 shadow-sm'
                : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            Reports
          </button>
          <button
            onClick={() => setActiveTab('skills')}
            className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
              activeTab === 'skills'
                ? 'bg-white text-slate-800 shadow-sm'
                : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            Skills
          </button>
          <button
            onClick={() => setActiveTab('generate')}
            className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
              activeTab === 'generate'
                ? 'bg-white text-slate-800 shadow-sm'
                : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            Generate
          </button>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {activeTab === 'workflow' && (
          <>
            <div className="flex-1">
              <FlowCanvas />
            </div>
            <DetailPanel />
          </>
        )}
        {activeTab === 'reports' && (
          <div className="flex-1">
            <ReportPanel />
          </div>
        )}
        {activeTab === 'skills' && (
          <div className="flex-1">
            <SkillSearch />
          </div>
        )}
        {activeTab === 'generate' && (
          <div className="flex-1">
            <SkillGenerator />
          </div>
        )}
      </div>
    </div>
  )
}
