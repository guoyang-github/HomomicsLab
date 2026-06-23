import { useState } from 'react'
import { AppLayout } from '@/components/layout/AppLayout'
import type { NavItem } from '@/components/layout/Sidebar'
import { ChatPanel } from '@/components/chat/ChatPanel'
import { Workspace } from '@/components/workspace/Workspace'
import { ReportPanel } from '@/components/reports/ReportPanel'
import { FileBrowser } from '@/components/files/FileBrowser'
import { FigureWorkbench } from '@/components/Figures'
import { SkillSearch } from '@/components/skills/SkillSearch'
import { SkillManager } from '@/components/skills/SkillManager'
import { SkillGenerator } from '@/components/skills/SkillGenerator'
import { DomainMarketplace } from '@/components/domains/DomainMarketplace'
import { SettingsPanel } from '@/components/settings/SettingsPanel'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui'
import { useTranslation } from '@/i18n'

function App() {
  const [activeItem, setActiveItem] = useState<NavItem>('chat')
  const { t } = useTranslation()

  const renderContent = () => {
    switch (activeItem) {
      case 'chat':
        return <ChatPanel />
      case 'workflow':
        return <Workspace />
      case 'reports':
        return <ReportPanel />
      case 'files':
        return <FileBrowser />
      case 'figures':
        return <FigureWorkbench />
      case 'skills':
        return (
          <div className="h-full p-4">
            <Tabs defaultValue="search" className="h-full rounded-xl border border-border bg-card shadow-card">
              <div className="border-b border-border px-4 pt-4">
                <TabsList>
                  <TabsTrigger value="search">{t('skills.tabs.search')}</TabsTrigger>
                  <TabsTrigger value="manage">{t('skills.tabs.manage')}</TabsTrigger>
                  <TabsTrigger value="generate">{t('skills.tabs.generate')}</TabsTrigger>
                </TabsList>
              </div>
              <div className="flex-1 overflow-hidden p-4 pt-0">
                <TabsContent value="search" className="h-full">
                  <SkillSearch />
                </TabsContent>
                <TabsContent value="manage" className="h-full">
                  <SkillManager />
                </TabsContent>
                <TabsContent value="generate" className="h-full">
                  <SkillGenerator />
                </TabsContent>
              </div>
            </Tabs>
          </div>
        )
      case 'domains':
        return <DomainMarketplace />
      case 'settings':
        return <SettingsPanel />
      default:
        return <ChatPanel />
    }
  }

  return (
    <AppLayout activeItem={activeItem} onNavigate={setActiveItem}>
      {renderContent()}
    </AppLayout>
  )
}

export default App
