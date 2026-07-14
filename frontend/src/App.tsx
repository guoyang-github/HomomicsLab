import { useCallback, useEffect, useState } from 'react'
import { AppLayout } from '@/components/layout/AppLayout'
import type { NavItem } from '@/components/layout/Sidebar'
import { ChatPanel } from '@/components/chat/ChatPanel'
import { FileBrowser } from '@/components/files/FileBrowser'
import { SkillSearch } from '@/components/skills/SkillSearch'
import { SkillManager } from '@/components/skills/SkillManager'
import { SkillGenerator } from '@/components/skills/SkillGenerator'
import { DomainMarketplace } from '@/components/domains/DomainMarketplace'
import { MCPMarketplace } from '@/components/mcp/MCPMarketplace'
import { SettingsPanel } from '@/components/settings/SettingsPanel'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui'
import { useTranslation } from '@/i18n'

const NAV_ITEMS: readonly NavItem[] = ['chat', 'files', 'skills', 'domains', 'mcp', 'settings']

// Hash routing: the active view is mirrored to window.location.hash
// (e.g. #/skills) so refreshes keep the view and links are shareable.
function navItemFromHash(): NavItem {
  const slug = window.location.hash.replace(/^#\/?/, '')
  return (NAV_ITEMS as readonly string[]).includes(slug) ? (slug as NavItem) : 'chat'
}

function App() {
  const [activeItem, setActiveItem] = useState<NavItem>(navItemFromHash)
  const { t } = useTranslation()

  useEffect(() => {
    const handleHashChange = () => setActiveItem(navItemFromHash())
    window.addEventListener('hashchange', handleHashChange)
    return () => window.removeEventListener('hashchange', handleHashChange)
  }, [])

  const handleNavigate = useCallback((item: NavItem) => {
    setActiveItem(item)
    const nextHash = `#/${item}`
    if (window.location.hash !== nextHash) {
      window.location.hash = nextHash
    }
  }, [])

  const renderContent = () => {
    switch (activeItem) {
      case 'chat':
        return <ChatPanel />
      case 'files':
        return <FileBrowser />
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
      case 'mcp':
        return <MCPMarketplace />
      case 'settings':
        return <SettingsPanel />
      default:
        return <ChatPanel />
    }
  }

  return (
    <AppLayout activeItem={activeItem} onNavigate={handleNavigate}>
      {renderContent()}
    </AppLayout>
  )
}

export default App
