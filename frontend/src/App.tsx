import { ChatPanel } from '@/components/chat/ChatPanel'

function App() {
  return (
    <div className="flex h-screen flex-col bg-slate-50">
      <header className="bg-primary px-4 py-3 text-white">
        <h1 className="text-lg font-bold">HomicsLab</h1>
      </header>
      <main className="flex flex-1 overflow-hidden">
        <div className="w-2/5 min-w-[360px] max-w-[480px]">
          <ChatPanel />
        </div>
        <div className="flex-1 bg-white p-4">
          <div className="flex h-full items-center justify-center rounded-lg border-2 border-dashed border-slate-200">
            <p className="text-slate-400">工作空间将在后续任务中实现</p>
          </div>
        </div>
      </main>
    </div>
  )
}

export default App
