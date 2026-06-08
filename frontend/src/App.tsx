import { ChatPanel } from '@/components/chat/ChatPanel'
import { Workspace } from '@/components/workspace/Workspace'

function App() {
  return (
    <div className="flex h-screen flex-col bg-slate-50">
      <header className="bg-primary px-4 py-3 text-white">
        <h1 className="text-lg font-bold">HomomicsLab</h1>
      </header>
      <main className="flex flex-1 overflow-hidden">
        <div className="w-2/5 min-w-[360px] max-w-[480px]">
          <ChatPanel />
        </div>
        <div className="flex-1">
          <Workspace />
        </div>
      </main>
    </div>
  )
}

export default App
