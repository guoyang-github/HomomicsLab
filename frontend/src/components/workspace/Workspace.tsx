import { useState } from 'react'
import { FlowCanvas } from './FlowCanvas'
import { DetailPanel } from './DetailPanel'
import { ReportPanel } from '@/components/reports/ReportPanel'
import { SkillSearch } from '@/components/skills/SkillSearch'
import { SkillManager } from '@/components/skills/SkillManager'
import { SkillGenerator } from '@/components/skills/SkillGenerator'
import { DomainMarketplace } from '@/components/domains/DomainMarketplace'

type WorkspaceTab = 'workflow' | 'reports' | 'skills' | 'generate' | 'domains'
type SkillView = 'search' | 'manage'

export function Workspace() {
  const [activeTab, setActiveTab] = useState<WorkspaceTab>('workflow')
  const [skillView, setSkillView] = useState<SkillView>('search')

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
          <button
            onClick={() => setActiveTab('domains')}
            className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
              activeTab === 'domains'
                ? 'bg-white text-slate-800 shadow-sm'
                : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            Domains
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
          <div className="flex flex-1 flex-col overflow-hidden">
            <div className="flex border-b border-slate-200 bg-white px-4 py-2">
              <button
                onClick={() => setSkillView('search')}
                className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
                  skillView === 'search'
                    ? 'bg-slate-100 text-slate-800'
                    : 'text-slate-500 hover:text-slate-700'
                }`}
              >
                Search
              </button>
              <button
                onClick={() => setSkillView('manage')}
                className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
                  skillView === 'manage'
                    ? 'bg-slate-100 text-slate-800'
                    : 'text-slate-500 hover:text-slate-700'
                }`}
              >
                Manage
              </button>
            </div>
            <div className="flex-1 overflow-hidden">
              {skillView === 'search' && <SkillSearch />}
              {skillView === 'manage' && <SkillManager />}
            </div>
          </div>
        )}
        {activeTab === 'generate' && (
          <div className="flex-1">
            <SkillGenerator />
          </div>
        )}
        {activeTab === 'domains' && (
          <div className="flex-1">
            <DomainMarketplace />
          </div>
        )}
      </div>
    </div>
  )
}
