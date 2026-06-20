import { useEffect, useRef } from 'react'
import { usePresence } from '@/api/collab'
import { PresenceCursors } from './PresenceCursors'
import { ActiveUsers } from './ActiveUsers'
import { useProjectStore } from '@/stores/projectStore'

const THROTTLE_MS = 80

export function CollabLayer() {
  const projectId = useProjectStore((state) => state.currentProjectId)
  const { users, isConnected, sendCursor } = usePresence(
    projectId === 'default' ? null : projectId,
    'me'
  )
  const lastSentRef = useRef(0)

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      const now = Date.now()
      if (now - lastSentRef.current < THROTTLE_MS) {
        return
      }
      lastSentRef.current = now
      sendCursor(e.clientX, e.clientY)
    }

    window.addEventListener('mousemove', handleMouseMove)
    return () => window.removeEventListener('mousemove', handleMouseMove)
  }, [sendCursor])

  return (
    <>
      <PresenceCursors users={users} />
      <div className="fixed bottom-4 right-4 z-40 rounded-full bg-white/80 px-3 py-1.5 shadow backdrop-blur dark:bg-slate-900/80">
        <ActiveUsers users={users} isConnected={isConnected} />
      </div>
    </>
  )
}
